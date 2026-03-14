$ProgressPreference = 'SilentlyContinue'

# Step 1: Check if 7zip is available, install if not
$7z = 'C:\Program Files\7-Zip\7z.exe'
if (-not (Test-Path $7z)) {
    Write-Output 'Installing 7-Zip...'
    $7zUrl = 'https://www.7-zip.org/a/7z2409-x64.exe'
    Invoke-WebRequest -Uri $7zUrl -OutFile 'C:\temp\7z-setup.exe'
    Start-Process -FilePath 'C:\temp\7z-setup.exe' -ArgumentList '/S' -Wait
    Write-Output '7-Zip installed'
}

# Step 2: Extract RAR (password: plc247.com)
Write-Output 'Extracting TwinCAT3.1.rar (password: plc247.com)...'
& $7z x 'C:\temp\TwinCAT3.1.rar' -o'C:\temp\TwinCAT3.1' -p'plc247.com' -aoa -y
Write-Output ''

# Step 3: List extracted contents
Write-Output 'Extracted contents:'
Get-ChildItem 'C:\temp\TwinCAT3.1' -Recurse -File | Select-Object FullName, @{N='SizeMB';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize
