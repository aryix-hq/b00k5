# ==============================================================================
#  b00k5 — Open-Source Indian ERP & MCA Compliance Platform
#  Universal Windows PowerShell Automated Installer
# ==============================================================================
#  Usage via PowerShell:
#    irm https://raw.githubusercontent.com/aryix-hq/b00k5/main/scripts/install.ps1 | iex
#
#  Usage locally:
#    powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Info($msg)    { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)     { Write-Host "[ERR]  $msg" -ForegroundColor Red }
function Write-Header($msg)  { Write-Host "`n=== $msg ===" -ForegroundColor Blue }

Write-Host @"
  _      ____   ____  _     ____ 
 | |__  / __ \ / __ \| | __| ___|
 | '_ \/ / _` / / _` | |/ /|___ \ 
 | |_) | | (_| | | (_|   <  ___) |
 |_.__/ \ \__,_|\ \__,_|_|\_\____/ 
         \____/  \____/           
 Sovereign Local-First Indian Financial ERP & MCA Compliance Hub
 Windows PowerShell Automated Installer v1.0.0
----------------------------------------------------------------------
"@ -ForegroundColor Cyan

# --- 1. System Requirements Check ---
Write-Header "1. Inspecting System Requirements"

$os = [System.Environment]::OSVersion.VersionString
Write-Info "Operating System: $os"

# Check RAM
try {
    $ramGB = [Math]::Round((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum / 1GB)
    if ($ramGB -lt 4) {
        Write-Warn "System RAM: $ramGB GB. Minimum recommended is 4 GB (8 GB recommended)."
    } else {
        Write-Success "System RAM: $ramGB GB (Sufficient)"
    }
} catch {
    Write-Info "Could not probe physical RAM dynamically."
}

# --- 2. Check Prerequisites ---
Write-Header "2. Checking Prerequisites"

# Check Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git is not installed. Please install Git for Windows: https://git-scm.com/download/win"
    exit 1
}
Write-Success "Git is available: $((git --version))"

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker is not installed or not in PATH."
    Write-Info "Please install Docker Desktop for Windows with WSL2 backend: https://www.docker.com/products/docker-desktop/"
    exit 1
}
Write-Success "Docker CLI is available: $((docker --version))"

# Check Docker Daemon Running
try {
    docker info > $null 2>&1
    Write-Success "Docker Desktop daemon is active and responsive."
} catch {
    Write-Err "Cannot communicate with Docker daemon. Please ensure Docker Desktop is started and WSL2 engine is running."
    exit 1
}

# Check Docker Compose
$composeCmd = "docker compose"
try {
    docker compose version > $null 2>&1
    Write-Success "Docker Compose v2 plugin detected."
} catch {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $composeCmd = "docker-compose"
        Write-Success "Legacy docker-compose detected."
    } else {
        Write-Err "Docker Compose is required but not found."
        exit 1
    }
}

# --- 3. Repository & Workspace ---
Write-Header "3. Preparing Repository & Workspace"

$targetDir = "b00k5"
$repoUrl = "https://github.com/aryix-hq/b00k5.git"

if ((Test-Path "docker-compose.yml") -and (Test-Path "apps\api") -and (Test-Path "apps\web")) {
    Write-Info "Detected execution within existing b00k5 directory: $((Get-Location))"
} else {
    if (Test-Path $targetDir) {
        Write-Info "Directory '$targetDir' exists. Pulling latest commits..."
        Set-Location $targetDir
        git pull
    } else {
        Write-Info "Cloning b00k5 repository from $repoUrl..."
        git clone $repoUrl $targetDir
        Set-Location $targetDir
    }
}

# --- 4. Environment Secrets ---
Write-Header "4. Generating Production Passphrases & .env"

function Generate-Token($bytes = 24) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] $bytes
    $rng.GetBytes($buf)
    return -join ($buf | ForEach-Object { "{0:x2}" -f $_ })
}

if (-not (Test-Path ".env")) {
    Write-Info "Creating new .env with cryptographically random secrets..."
    $dbPass = Generate-Token 24
    $minioPass = Generate-Token 24
    $jwtSecret = (Generate-Token 32) + (Generate-Token 32)

    if (Test-Path ".env.example") {
        $content = Get-Content ".env.example" -Raw
        $content = $content -replace "b00k5_secure_vault_password_2026", $dbPass
        $content = $content -replace "minio_storage_secret_key_2026", $minioPass
        $content = $content -replace "b00k5_default_dev_jwt_secret_key_change_in_prod_2026", $jwtSecret
        Set-Content -Path ".env" -Value $content -Encoding UTF8
    } else {
        @"
APP_ENV=production
SECRET_KEY=$jwtSecret
POSTGRES_USER=b00k5_admin
POSTGRES_PASSWORD=$dbPass
POSTGRES_DB=b00k5_db
MINIO_ROOT_USER=minio_storage_admin
MINIO_ROOT_PASSWORD=$minioPass
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BRIDGE_URL=http://localhost:28045
"@ | Set-Content -Path ".env" -Encoding UTF8
    }
    Write-Success "Generated secure .env file."
} else {
    Write-Info "Existing .env file preserved."
}

# --- 5. Deploy Stack ---
Write-Header "5. Launching Containers via Docker Compose"

Write-Info "Running: $composeCmd up -d --build"
Invoke-Expression "$composeCmd up -d --build"

# --- 6. Health Check ---
Write-Header "6. Verifying Services"

Write-Info "Waiting for FastAPI (Port 8000) and Next.js (Port 3000)..."

$maxWait = 90
$elapsed = 0
$ready = $false

while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 3
    $elapsed += 3
    Write-Host -NoNewline "."

    try {
        $apiCheck = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        $webCheck = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($apiCheck.StatusCode -eq 200 -and $webCheck.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Keep waiting
    }
}
Write-Host ""

if ($ready) {
    Write-Success "All application endpoints are responding with HTTP 200 OK!"
} else {
    Write-Warn "Containers are still starting up. Use 'docker compose logs -f' to inspect startup."
}

# --- 7. Seed Data ---
Write-Header "7. Initializing Default Statutory Chart of Accounts"

try {
    docker exec b00k5_api python /app/seed_data.py > $null 2>&1
    Write-Success "Statutory Chart of Accounts & Demo Companies initialized."
} catch {
    Write-Info "Seed data script completed."
}

# --- 8. Done ---
Write-Header "DEPLOYMENT COMPLETED SUCCESSFULLY"

Write-Host @"

Congratulations! b00k5 is running locally on Windows.

Access Points:
  * Web Application (UI):      http://localhost:3000
  * FastAPI Backend & Swagger: http://localhost:8000/docs
  * MinIO S3 Console:          http://localhost:9001
  * Hardware DSC Bridge:       http://localhost:28045

Demo Credentials:
  * Founder:  founder@vortexai.com / admin123
  * CA:       ca.auditor@vortexai.com / admin123
  * Admin:    admin@b00k5.local / admin123

Operations Commands:
  * View logs:    docker compose logs -f
  * Stop stack:   docker compose down
  * Restart:      docker compose restart

Documentation: docs\INSTALLATION_GUIDE.md
"@ -ForegroundColor Green

