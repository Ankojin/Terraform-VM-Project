
Python code will import the information from the CSV and write to the terraform configuration.

This script is a Terraform configuration that defines resources for deploying either a Linux or Windows virtual machine (VM) on Microsoft Azure, with additional features such as data disks and custom provisioning. Here's a breakdown of the key sections:

1. Linux VM Configuration:
**Resource Type: azurerm_linux_virtual_machine.**
Properties:
Specifies the VM name, resource group, location, and size.
Uses network interfaces and assigns an admin username/password.
Defines an OS disk with caching and storage account type settings.
Sets the OS image with the publisher, offer, SKU, and version.
**Adds tags and custom data (cloud-init) for initialization.
Data Disks:
Additional disks are created using the azurerm_managed_disk resource and then attached using the azurerm_virtual_machine_data_disk_attachment resource.**

2. Windows VM Configuration:
**Resource Type: azurerm_windows_virtual_machine.**
Properties:
Similar to the Linux VM but configured for Windows VMs.
Includes a Custom data runs a PowerShell script to join the VM to an Active Directory domain.
Data Disks:
As with the Linux VM, additional disks are created and attached.

3. Common Configuration for Both OS Types:
Network Interfaces: Both VM types reference network interfaces for connectivity.
**Disk Attachments: Data disks are defined separately and attached to the VM using the azurerm_virtual_machine_data_disk_attachment resource**.
**Tags: Tags are dynamically generated based on tags_str, which likely contains key-value pairs for resource categorization.**
**Things to Note:**
The is_windows flag determines which configuration block is executed.
Custom Cloud-Init: For Linux, cloud-init scripts are used, which could automate software installations, configurations, or other initial setup tasks. For Windows, a PowerShell script is used to join the domain.
Data Disk Attachment: Each additional disk is defined with properties like disk_size_gb, storage_type, and lun, then attached to the VM.

Prerequisites.
1. Install Python
2. Install Terrform
3. csv file

Steps to run python and Terraform

1. python generate-tf.py ( it will generate the tf in the output path( mentioned in script).



