# Video Generator Service Demo

This PowerShell script demonstrates the new video generation capabilities of the AI Advertisement Generator.

# Prerequisites: Make sure all services are running
# docker-compose up --build

Write-Host "🎬 AI Advertisement Generator - Video Demo" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check if services are running
Write-Host "`n🔍 Checking service health..." -ForegroundColor Yellow

try {
    $orchestratorHealth = Invoke-RestMethod -Uri "http://localhost:8000/docs" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ Orchestrator service is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Orchestrator service is not running. Please start with: docker-compose up" -ForegroundColor Red
    exit 1
}

try {
    $videoGeneratorHealth = Invoke-RestMethod -Uri "http://localhost:5003/" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ Video Generator service is running" -ForegroundColor Green
    Write-Host "   Supported animations: $($videoGeneratorHealth.supported_animations -join ', ')" -ForegroundColor Gray
    Write-Host "   Supported styles: $($videoGeneratorHealth.supported_styles -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "❌ Video Generator service is not running" -ForegroundColor Red
    exit 1
}

# Demo 1: Generate complete ad campaign with video
Write-Host "`n🎯 Demo 1: Complete Ad Campaign with Video" -ForegroundColor Yellow
Write-Host "===========================================" -ForegroundColor Yellow

$campaignRequest = @{
    product = "Professional Gaming Mouse"
    audience = "competitive gamers"
    tone = "intense and professional"
    ASIN = "B07KCDB6GB"
    brand_text = "ProGamer Elite"
    cta_text = "Dominate Now!"
    generate_video = $true
    video_animation = "ken_burns"
    video_duration = 6
    video_style = "dramatic"
} | ConvertTo-Json

Write-Host "📤 Sending request for complete ad campaign..." -ForegroundColor Cyan
Write-Host "⏱️  This may take 30-60 seconds..." -ForegroundColor Gray

try {
    $startTime = Get-Date
    $campaignResponse = Invoke-RestMethod -Uri "http://localhost:8000/run" -Method Post -Body $campaignRequest -ContentType "application/json"
    $duration = ((Get-Date) - $startTime).TotalSeconds
    
    Write-Host "✅ Campaign generated successfully in $([math]::Round($duration, 1)) seconds!" -ForegroundColor Green
    Write-Host "`n📝 Generated Ad Text:" -ForegroundColor Cyan
    Write-Host "   Product: $($campaignResponse.ad_text.product)" -ForegroundColor White
    Write-Host "   Features: $($campaignResponse.ad_text.features -join ', ')" -ForegroundColor White
    Write-Host "   Description: $($campaignResponse.ad_text.description.Substring(0, [Math]::Min($campaignResponse.ad_text.description.Length, 100)))..." -ForegroundColor White
    
    Write-Host "`n🖼️  Image URL: $($campaignResponse.image_url)" -ForegroundColor Cyan
    if ($campaignResponse.video_url) {
        Write-Host "🎬 Video URL: $($campaignResponse.video_url)" -ForegroundColor Cyan
        $videoFilename = $campaignResponse.video_url.Split('/')[-1]
        
        # Download the video for demonstration
        Write-Host "`n📥 Downloading video for preview..." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri $campaignResponse.video_url -OutFile "demo_campaign_video.mp4"
            $videoSize = (Get-Item "demo_campaign_video.mp4").Length / 1MB
            Write-Host "✅ Video downloaded as 'demo_campaign_video.mp4' ($([math]::Round($videoSize, 1)) MB)" -ForegroundColor Green
        } catch {
            Write-Host "❌ Failed to download video: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    $imageFilename = $campaignResponse.image_url.Split('/')[-1]
    
} catch {
    Write-Host "❌ Campaign generation failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Demo 2: Generate video from existing image
Write-Host "`n🎬 Demo 2: Video-Only Generation from Existing Image" -ForegroundColor Yellow
Write-Host "====================================================" -ForegroundColor Yellow

if ($campaignResponse.image_url) {
    $videoOnlyRequest = @{
        image_url = $campaignResponse.image_url
        animation_type = "zoom_pan"
        duration = 4
        fps = 30
        style = "smooth"
        text_overlay = "Smooth Zoom Effect"
        brand_text = "ProGamer Elite"
        cta_text = "Experience the Difference!"
    } | ConvertTo-Json
    
    Write-Host "📤 Generating zoom_pan video from existing image..." -ForegroundColor Cyan
    
    try {
        $startTime = Get-Date
        $videoResponse = Invoke-RestMethod -Uri "http://localhost:8000/generate-video" -Method Post -Body $videoOnlyRequest -ContentType "application/json"
        $duration = ((Get-Date) - $startTime).TotalSeconds
        
        Write-Host "✅ Video generated successfully in $([math]::Round($duration, 1)) seconds!" -ForegroundColor Green
        Write-Host "   File size: $($videoResponse.file_size_mb) MB" -ForegroundColor White
        Write-Host "   Duration: $($videoResponse.duration_seconds) seconds" -ForegroundColor White
        Write-Host "   FPS: $($videoResponse.fps)" -ForegroundColor White
        Write-Host "   Animation: $($videoResponse.animation_type)" -ForegroundColor White
        Write-Host "   Expires in: $($videoResponse.expires_in_minutes) minutes" -ForegroundColor White
        
        # Download this video too
        Write-Host "`n📥 Downloading second video..." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri $videoResponse.video_url -OutFile "demo_zoom_pan_video.mp4"
            Write-Host "✅ Video downloaded as 'demo_zoom_pan_video.mp4'" -ForegroundColor Green
        } catch {
            Write-Host "❌ Failed to download video: $($_.Exception.Message)" -ForegroundColor Red
        }
        
    } catch {
        Write-Host "❌ Video generation failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Demo 3: Try different animation types
Write-Host "`n🎨 Demo 3: Animation Showcase" -ForegroundColor Yellow
Write-Host "=============================" -ForegroundColor Yellow

$animations = @("parallax", "fade_effects")
$styles = @("gentle", "energetic")

foreach ($i in 0..($animations.Length - 1)) {
    $animation = $animations[$i]
    $style = $styles[$i]
    
    Write-Host "`n🎭 Testing $animation animation with $style style..." -ForegroundColor Cyan
    
    $animationRequest = @{
        image_url = $campaignResponse.image_url
        animation_type = $animation
        duration = 3
        fps = 30
        style = $style
        brand_text = "ProGamer Elite"
    } | ConvertTo-Json
    
    try {
        $startTime = Get-Date
        $animationResponse = Invoke-RestMethod -Uri "http://localhost:8000/generate-video" -Method Post -Body $animationRequest -ContentType "application/json"
        $duration = ((Get-Date) - $startTime).TotalSeconds
        
        Write-Host "✅ $animation video created in $([math]::Round($duration, 1)) seconds ($($animationResponse.file_size_mb) MB)" -ForegroundColor Green
        
        # Download for collection
        try {
            Invoke-WebRequest -Uri $animationResponse.video_url -OutFile "demo_${animation}_video.mp4"
            Write-Host "   📁 Saved as 'demo_${animation}_video.mp4'" -ForegroundColor Gray
        } catch {
            Write-Host "   ❌ Download failed" -ForegroundColor Red
        }
        
    } catch {
        Write-Host "❌ $animation generation failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Summary
Write-Host "`n🎉 Demo Complete!" -ForegroundColor Green
Write-Host "================" -ForegroundColor Green

Write-Host "`n📂 Generated Files:" -ForegroundColor Cyan
Get-ChildItem -Path "." -Filter "demo_*.mp4" | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 1)
    Write-Host "   🎬 $($_.Name) ($size MB)" -ForegroundColor White
}

Write-Host "`n🔗 API Endpoints Demonstrated:" -ForegroundColor Cyan
Write-Host "   📝 POST /run (with generate_video=true)" -ForegroundColor White
Write-Host "   🎬 POST /generate-video" -ForegroundColor White
Write-Host "   📥 GET /download-video/{filename}" -ForegroundColor White

Write-Host "`n🎨 Animation Types Tested:" -ForegroundColor Cyan
Write-Host "   🔄 ken_burns (dramatic style)" -ForegroundColor White
Write-Host "   🔍 zoom_pan (smooth style)" -ForegroundColor White
Write-Host "   🌊 parallax (gentle style)" -ForegroundColor White
Write-Host "   ✨ fade_effects (energetic style)" -ForegroundColor White

Write-Host "`n⚠️  Note: Generated videos expire automatically:" -ForegroundColor Yellow
Write-Host "   ⏰ Campaign video expires in 15 minutes" -ForegroundColor Gray
Write-Host "   ⏰ Other videos expire in 15 minutes" -ForegroundColor Gray

Write-Host "`n🎯 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. 📺 Open generated MP4 files to view results" -ForegroundColor White
Write-Host "   2. 🔧 Experiment with different animation parameters" -ForegroundColor White
Write-Host "   3. 🌐 Check service documentation at http://localhost:8000/docs" -ForegroundColor White
Write-Host "   4. 📖 View video service docs at http://localhost:5003/docs" -ForegroundColor White

Write-Host "`n✨ Video Generation Layer Successfully Demonstrated! ✨" -ForegroundColor Green