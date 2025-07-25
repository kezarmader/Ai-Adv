# AI Advertisement Generator - Health Check Script
# PowerShell version for Windows users

param(
    [switch]$Detailed,
    [switch]$Monitor,
    [int]$MonitorInterval = 30
)

# Service endpoints
$Services = @{
    "orchestrator" = "http://localhost:8000"
    "image-generator" = "http://localhost:5001"
    "poster-service" = "http://localhost:5002"
    "llm-service" = "http://localhost:11434"
}

function Test-ServiceHealth {
    param(
        [string]$Name,
        [string]$BaseUrl
    )
    
    try {
        $endpoint = if ($Name -eq "llm-service") { "$BaseUrl/api/tags" } else { "$BaseUrl/docs" }
        
        $response = Invoke-WebRequest -Uri $endpoint -TimeoutSec 5 -UseBasicParsing
        
        return @{
            Status = "✅ Healthy"
            ResponseTime = if ($response.Headers.ContainsKey('X-Response-Time')) { $response.Headers['X-Response-Time'] } else { "N/A" }
            StatusCode = $response.StatusCode
        }
    }
    catch [System.Net.WebException] {
        return @{
            Status = "❌ Unreachable"
            ResponseTime = $null
            StatusCode = $null
            Error = $_.Exception.Message
        }
    }
    catch {
        return @{
            Status = "❌ Error"
            ResponseTime = $null
            StatusCode = $null
            Error = $_.Exception.Message
        }
    }
}

function Test-AdGeneration {
    $payload = @{
        product = "Test Product"
        audience = "tech enthusiasts"
        tone = "friendly"
        ASIN = "B08N5WRWNW"
        brand_text = "TestBrand"
        cta_text = "Try Now!"
    } | ConvertTo-Json

    try {
        Write-Host "🧪 Testing ad generation pipeline..." -ForegroundColor Yellow
        
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        
        $response = Invoke-RestMethod -Uri "$($Services['orchestrator'])/run" -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 60
        
        $stopwatch.Stop()
        $duration = $stopwatch.Elapsed.TotalSeconds
        
        return @{
            Status = "✅ Success"
            Duration = "$([math]::Round($duration, 2))s"
            HasAdText = $response.PSObject.Properties.Name -contains "ad_text"
            HasImageUrl = $response.PSObject.Properties.Name -contains "image_url"
            PostStatus = $response.post_status.status
        }
    }
    catch {
        return @{
            Status = "❌ Failed"
            Duration = if ($stopwatch) { "$([math]::Round($stopwatch.Elapsed.TotalSeconds, 2))s" } else { "N/A" }
            Error = $_.Exception.Message.Substring(0, [Math]::Min(100, $_.Exception.Message.Length))
        }
    }
}

function Show-ServiceStatus {
    Write-Host "`n📊 Service Health Status:" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Gray
    
    $results = @()
    
    foreach ($service in $Services.GetEnumerator()) {
        $result = Test-ServiceHealth -Name $service.Key -BaseUrl $service.Value
        
        $results += [PSCustomObject]@{
            Service = $service.Key
            Status = $result.Status
            ResponseTime = if ($result.ResponseTime) { $result.ResponseTime } else { "N/A" }
        }
    }
    
    $results | Format-Table -AutoSize
    
    return $results
}

function Show-PipelineTest {
    Write-Host "`n🔄 Pipeline Test:" -ForegroundColor Cyan
    
    $result = Test-AdGeneration
    
    foreach ($property in $result.GetEnumerator()) {
        Write-Host "  $($property.Key): $($property.Value)"
    }
    
    return $result
}

function Show-LogSummary {
    if ($Detailed) {
        Write-Host "`n📋 Recent Log Summary:" -ForegroundColor Cyan
        
        try {
            # Get recent errors from logs
            $errors = docker-compose logs --tail=50 | Select-String '"level":"ERROR"' | Select-Object -Last 5
            
            if ($errors) {
                Write-Host "Recent Errors:" -ForegroundColor Red
                foreach ($error in $errors) {
                    $timestamp = ($error -split '"timestamp":"')[1] -split '"')[0]
                    $message = ($error -split '"message":"')[1] -split '"')[0]
                    Write-Host "  [$timestamp] $message" -ForegroundColor Red
                }
            } else {
                Write-Host "✅ No recent errors found" -ForegroundColor Green
            }
            
            # Performance metrics
            $slowRequests = docker-compose logs --tail=100 | Select-String '"duration_ms":[0-9]{4,}' | Measure-Object
            Write-Host "`nPerformance:" -ForegroundColor Yellow
            Write-Host "  Slow requests (>1s) in last 100 logs: $($slowRequests.Count)"
            
        } catch {
            Write-Host "Could not analyze logs. Make sure Docker Compose is running." -ForegroundColor Red
        }
    }
}

function Start-ContinuousMonitoring {
    Write-Host "🔄 Starting continuous monitoring (every $MonitorInterval seconds)" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
    
    while ($true) {
        Clear-Host
        Write-Host "🏥 AI Advertisement Generator - Health Monitor" -ForegroundColor Green
        Write-Host "📅 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
        
        $serviceResults = Show-ServiceStatus
        $pipelineResult = Show-PipelineTest
        
        # Summary
        $healthyCount = ($serviceResults | Where-Object { $_.Status -like "*✅*" }).Count
        $totalCount = $serviceResults.Count
        
        Write-Host "`n📝 Summary:" -ForegroundColor Cyan
        if ($healthyCount -eq $totalCount -and $pipelineResult.Status -like "*✅*") {
            Write-Host "🎉 All systems operational!" -ForegroundColor Green
        } elseif ($healthyCount -eq $totalCount) {
            Write-Host "⚠️ Services healthy but pipeline has issues" -ForegroundColor Yellow
        } else {
            Write-Host "❌ $($totalCount - $healthyCount)/$totalCount services have issues" -ForegroundColor Red
        }
        
        Write-Host "`nNext check in $MonitorInterval seconds..." -ForegroundColor Gray
        Start-Sleep -Seconds $MonitorInterval
    }
}

# Main execution
Write-Host "🏥 AI Advertisement Generator - Health Check" -ForegroundColor Green
Write-Host "📅 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ("=" * 60) -ForegroundColor Gray

if ($Monitor) {
    Start-ContinuousMonitoring
} else {
    $serviceResults = Show-ServiceStatus
    $pipelineResult = Show-PipelineTest
    Show-LogSummary
    
    # Final summary
    $healthyCount = ($serviceResults | Where-Object { $_.Status -like "*✅*" }).Count
    $totalCount = $serviceResults.Count
    
    Write-Host "`n📝 Summary:" -ForegroundColor Cyan
    if ($healthyCount -eq $totalCount -and $pipelineResult.Status -like "*✅*") {
        Write-Host "🎉 All systems operational!" -ForegroundColor Green
        exit 0
    } elseif ($healthyCount -eq $totalCount) {
        Write-Host "⚠️ Services healthy but pipeline has issues" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "❌ $($totalCount - $healthyCount)/$totalCount services have issues" -ForegroundColor Red
        exit 1
    }
}
