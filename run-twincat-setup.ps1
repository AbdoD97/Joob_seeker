# Run TwinCAT 3.1 installer silently with XAR (runtime) components
$installer = 'C:\temp\TwinCAT3.1\TC31-FULL-Setup.3.1.4024.12.exe'

Write-Output 'Starting TwinCAT 3.1 installer (silent mode)...'
Write-Output 'This may take several minutes...'

# Start the installer - try silent first
# TwinCAT uses standard InstallShield/MSI, try /s or /quiet
$proc = Start-Process -FilePath $installer -ArgumentList '/s /v"/qn REBOOT=ReallySuppress"' -Wait -PassThru
Write-Output "Installer exit code: $($proc.ExitCode)"

# Check if TwinCAT was installed
$tcPath = 'C:\TwinCAT'
if (Test-Path $tcPath) {
    Write-Output 'TwinCAT installed successfully!'
    Get-ChildItem $tcPath -Depth 1 | Select-Object FullName | Format-Table -AutoSize
} else {
    Write-Output 'TwinCAT directory not found at C:\TwinCAT'
    Write-Output 'Checking Program Files...'
    Get-ChildItem 'C:\Program Files\Beckhoff' -ErrorAction SilentlyContinue -Depth 1 | Select-Object FullName | Format-Table -AutoSize
    Get-ChildItem 'C:\Program Files (x86)\Beckhoff' -ErrorAction SilentlyContinue -Depth 1 | Select-Object FullName | Format-Table -AutoSize
}
