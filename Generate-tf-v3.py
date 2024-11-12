import base64
import csv

# Define paths for the CSV file and output Terraform file
csv_file_path = "./migration-vms-list.csv"
output_tf_file = "./main-v1.tf"
cloud_init_file = "./cloud-init-azure-disk.yaml"  # Path to cloud-init file
# Function to read the cloud-init YAML file
def read_and_encode_cloud_init_yaml(file_path):
    try:
        with open(file_path, 'r') as f:
            # Read file and encode in Base64
            content = f.read()
            encoded_content = base64.b64encode(content.encode()).decode()
            return encoded_content
    except FileNotFoundError:
        print(f"Cloud-init file {file_path} not found.")
        return ""

# Read and encode the cloud-init file
cloud_init_content = read_and_encode_cloud_init_yaml(cloud_init_file)

# Function to parse tags from CSV
def parse_tags(tags_str):
    tags = {}
    if tags_str:
        tag_pairs = tags_str.split(';')
        for pair in tag_pairs:
            if '=' in pair:  # Ensure there's an '=' in each pair
                key, value = pair.split('=', 1)  # Split by `=`
                # Strip spaces and extra quotes
                tags[key.strip().strip('"')] = value.strip().strip('"')
    return tags

# Open the output Terraform file to write the configuration
with open(output_tf_file, "w") as tf_file:
    # Write the provider block with environment-based authentication
    tf_file.write("""
variable "subscription_id" {
  description = "Default subscription_id."
  type        = string
  default     = "d88f0b5b-6660-4607-8c6a-395820400912"
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "location" {
  description = "Location for resources."
  type        = string
  default     = "Sweden Central"
}
""")

    # Dictionary to store unique provider aliases
    provider_aliases = {}

    # Read the CSV file and generate Terraform configuration for each VM
    with open(csv_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            vm_name = row["vm_name"]
            resource_group = row["resource_group"]
            vnet = row["vnet"]
            vnet_rg = row["vnet_rg"]
            subnet = row["subnet"]
            subnet_rg = row["subnet_rg"]
            subscription = row["subscription"]
            vm_size = row["vm_size"]
            os_publisher = row["os_publisher"]
            os_offer = row["os_offer"]
            os_sku = row["os_sku"]
            os_version = row["os_version"]
            custom_data = row["custom_data"]
            is_windows = row["is_windows"].lower() == "true"
            storage_account = row["storage_account"]  # Storage account for boot diagnostics
            cloud_init_path = row["cloud_init_path"]
            static_ip = row["static_ip"]
            tags = parse_tags(row["tags"])

            # Collect additional disks information
            additional_disks = []
            for idx in range(1, 10):  # Assuming a maximum of 10 additional disks per VM
                lun = row.get(f"disk_lun_{idx}")
                disk_name = row.get(f"disk_name_{idx}")
                storage_type = row.get(f"storage_type_{idx}")
                disk_size_gb = row.get(f"disk_size_gb_{idx}")
                if lun and disk_name and storage_type and disk_size_gb:
                    additional_disks.append({
                        "lun": lun,
                        "disk_name": disk_name,
                        "storage_type": storage_type,
                        "disk_size_gb": disk_size_gb
                    })

                  # Set up a provider alias for each subscription if not already done
            if subscription not in provider_aliases:
                provider_aliases[subscription] = f"provider_{subscription.replace('-', '_')}"
                tf_file.write(f"""

provider "azurerm" {{
  alias           = "{provider_aliases[subscription]}"
  features        {{}}
  subscription_id = "{subscription}"
}}
""")

            # Data sources for resource group, VNet, and subnet, using provider alias
            tf_file.write(f"""
resource "azurerm_resource_group" "{vm_name}_rg" {{
  name     = "{resource_group}"
  location = var.location
  provider = azurerm.{provider_aliases[subscription]}
}}

data "azurerm_resource_group" "{vm_name}_vnet_rg" {{
  name     = "{vnet_rg}"
  provider = azurerm.{provider_aliases[subscription]}
}}

data "azurerm_virtual_network" "{vm_name}_vnet" {{
  name                = "{vnet}"
  resource_group_name = data.azurerm_resource_group.{vm_name}_vnet_rg.name
  provider            = azurerm.{provider_aliases[subscription]}
}}

data "azurerm_subnet" "{vm_name}_subnet" {{
  name                 = "{subnet}"
  virtual_network_name = data.azurerm_virtual_network.{vm_name}_vnet.name
  resource_group_name  = data.azurerm_resource_group.{vm_name}_vnet_rg.name
  provider             = azurerm.{provider_aliases[subscription]}
}}
""")

            # Configure the network interface with a static IP
            tf_file.write(f"""
resource "azurerm_network_interface" "{vm_name}_nic" {{
  name                = "{vm_name}-nic"
  location            = var.location
  resource_group_name = resource.azurerm_resource_group.{vm_name}_rg.name
  provider            = azurerm.{provider_aliases[subscription]}

  ip_configuration {{
    name                          = "internal"
    subnet_id                     = data.azurerm_subnet.{vm_name}_subnet.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "{static_ip}"
  }}

}}
""")

            # Apply tags dynamically
            tags_str = ",\n  ".join([f'"{k}" = "{v}"' for k, v in tags.items()])
            
            # Configure the Linux or Windows VM with respective settings
            if not is_windows:
                tf_file.write(f"""
resource "azurerm_linux_virtual_machine" "{vm_name}" {{
  name                = "{vm_name}"
  resource_group_name = resource.azurerm_resource_group.{vm_name}_rg.name
  location            = var.location
  size                = "{vm_size}"
  provider            = azurerm.{provider_aliases[subscription]}

  network_interface_ids = [
    azurerm_network_interface.{vm_name}_nic.id
  ]
  admin_username = "azureuser"
  admin_password = "P@ssw0rd1234!"
  disable_password_authentication = "false"

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }}

  source_image_reference {{
    publisher = "{os_publisher}"
    offer     = "{os_offer}"
    sku       = "{os_sku}"
    version   = "{os_version}"
  }}
  tags = {{
    {tags_str}
  }}
  
  custom_data = "{cloud_init_content}"
  boot_diagnostics {{
   storage_account_uri = "https://{storage_account}.blob.core.windows.net/"
  }}
  
  }}
""")  

                # Add additional data disks for Linux VM
                for disk in additional_disks:
                    tf_file.write(f"""
resource "azurerm_managed_disk" "{disk['disk_name']}" {{
  name                 = "{disk['disk_name']}"
  location             = var.location
  resource_group_name  = resource.azurerm_resource_group.{vm_name}_rg.name
  provider             = azurerm.{provider_aliases[subscription]}
  storage_account_type = "{disk['storage_type']}"
  disk_size_gb         = {disk['disk_size_gb']}
  create_option        = "Empty"  
}}

resource "azurerm_virtual_machine_data_disk_attachment" "{vm_name}_{disk['disk_name']}_attachment" {{
  managed_disk_id    = azurerm_managed_disk.{disk['disk_name']}.id
  virtual_machine_id = azurerm_linux_virtual_machine.{vm_name}.id
  lun                = {disk['lun']}
  create_option      = "Attach"
  caching            = "ReadWrite"
}}

""")
            else:
                if is_windows:
                    tf_file.write(f"""
resource "azurerm_windows_virtual_machine" "{vm_name}" {{
  name                = "{vm_name}"
  resource_group_name = resource.azurerm_resource_group.{vm_name}_rg.name
  location            = var.location
  size                = "{vm_size}"
  provider            = azurerm.{provider_aliases[subscription]}

  network_interface_ids = [
    azurerm_network_interface.{vm_name}_nic.id
  ]

  admin_username = "azureuser"
  admin_password = "P@ssw0rd1234!"

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }}

  source_image_reference {{
    publisher = "{os_publisher}"
    offer     = "{os_offer}"
    sku       = "{os_sku}"
    version   = "{os_version}"
  }}

  tags = {{
    {tags_str}
  }}
  boot_diagnostics {{
   storage_account_uri = "https://{storage_account}.blob.core.windows.net/"
  }}

}}

                # Custom Script extension for Windows VM

resource "azurerm_virtual_machine_extension" "{vm_name}_Custom_Script" {{
  name                 = "{vm_name}-DomainJoin"
  virtual_machine_id   = azurerm_windows_virtual_machine.{vm_name}.id
  publisher            = "Microsoft.Compute"
  type                 = "CustomScriptExtension"
  type_handler_version = "1.9"

  settings = <<SETTINGS
    {{
        "fileUris": ["https://{storage_account}.blob.core.windows.net/postconf-script/postconf-script.ps1"],
        "commandToExecute": "powershell -ExecutionPolicy Unrestricted -file postconf-script.ps1 -EnableCredSSP -DisableBasicAuth"
    }}
SETTINGS
      
}}

""")
              
          # Add additional data disks for Windows VM
                for disk in additional_disks:
                      tf_file.write(f"""
resource "azurerm_managed_disk" "{disk['disk_name']}" {{
  name                 = "{disk['disk_name']}"
  location             = var.location
  resource_group_name  = resource.azurerm_resource_group.{vm_name}_rg.name
  provider             = azurerm.{provider_aliases[subscription]}
  storage_account_type = "{disk['storage_type']}"
  disk_size_gb         = {disk['disk_size_gb']}
  create_option        = "Empty" 
}}

resource "azurerm_virtual_machine_data_disk_attachment" "{vm_name}_{disk['disk_name']}_attachment" {{
  managed_disk_id    = azurerm_managed_disk.{disk['disk_name']}.id
  virtual_machine_id = azurerm_windows_virtual_machine.{vm_name}.id
  lun                = {disk['lun']}
  create_option      = "Attach"
  caching            = "ReadWrite"
}}

""")

    print("Terraform configuration has been generated in main-v1.tf")