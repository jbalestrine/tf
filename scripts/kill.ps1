Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess -Force
