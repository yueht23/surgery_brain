# this file is used to run auto package the project

# step 1. delete the old package ./dist/*
Remove-Item -Path ./dist/a/* -Recurse -Force
echo "delete the old package ./dist/a/*"

# step 2. package the project
pyinstaller.exe --collect-data pulp a.py -y
echo "package the project"

# step 3. copy the data base
# Copy-Item -Path .\surgery_brain\Data\ -Destination .\dist\a\surgery_brain\ -Recurse
echo "copy the data base"

# step 4. mkdir the logs
mkdir .\dist\a\logs\
echo "mkdir the logs folder"

# step 5. zip the package and the file name is string of the time
# using the winrar to zip the package
# the rar.exe is in the path C:\Program Files\WinRAR
$now = Get-Date -Format  "yyyy-MM-dd-HH-mm"
$zipName = "./dist/a-" + $now + ".rar"
& "C:\Program Files\WinRAR\rar.exe" a -r -ep1 -ibck -m5 -o+ -r -s -tl -y $zipName .\dist\a\
echo "zip the package and the file name is string of the time"
