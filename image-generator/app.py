from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from diffusers import (
    StableDiffusionXLPipeline,
    StableDiffusionXLImg2ImgPipeline,
    EulerAncestralDiscreteScheduler
)
from PIL import Image, ImageDraw, ImageFont
import torch, uuid, os, time, threading
from transformers import CLIPTokenizer

app = FastAPI()
clip_tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")

# Create images directory if it doesn't exist
IMAGES_DIR = "/tmp/images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# Mount static files for serving images
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Dictionary to track image creation times for cleanup
image_timestamps = {}

# Load SDXL base
pipe = StableDiffusionXLPipeline.from_pretrained(
    "playgroundai/playground-v2-1024px-aesthetic",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True
).to("cuda")

pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)

# Load SDXL refiner
refiner = StableDiffusionXLImg2ImgPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-refiner-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True
).to("cuda")


# Input model
class ImagePrompt(BaseModel):
    product_name: str
    features: list[str]
    brand_text: str
    cta_text: str
    scene: str


# Utility: add branding/CTA overlays
def add_overlay(image: Image.Image, brand: str, product: str, cta: str) -> Image.Image:
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    font_brand = ImageFont.truetype(font_path, 36)
    font_product = ImageFont.truetype(font_path, 28)
    font_cta = ImageFont.truetype(font_path, 24)

    # Top-left: brand and product
    draw.text((30, 20), brand, fill="blue", font=font_brand)
    draw.text((30, 70), product, fill="orange", font=font_product)

    # Bottom-left: CTA
    draw.text((30, image.height - 50), cta, fill="black", font=font_cta)
    draw.text((image.width - (image.width * 0.5), image.height - 50), "AI Generated", font=font_cta)

    return image

def trim_prompt(prompt: str, max_tokens: int = 77) -> str:
    tokens = clip_tokenizer(prompt, truncation=True, max_length=max_tokens, return_tensors="pt")
    decoded = clip_tokenizer.decode(tokens["input_ids"][0], skip_special_tokens=True)
    return decoded

def cleanup_image(image_path: str, filename: str):
    """Delete image file after 10 minutes"""
    time.sleep(600)  # 10 minutes = 600 seconds
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            print(f"Cleaned up image: {filename}")
        # Remove from tracking dictionary
        if filename in image_timestamps:
            del image_timestamps[filename]
    except Exception as e:
        print(f"Error cleaning up image {filename}: {e}")

def schedule_cleanup(image_path: str, filename: str):
    """Schedule image cleanup in a background thread"""
    cleanup_thread = threading.Thread(target=cleanup_image, args=(image_path, filename))
    cleanup_thread.daemon = True
    cleanup_thread.start()

# Main route
@app.post("/generate")
def generate_ad(data: ImagePrompt):
    print('generating image', ImagePrompt)

    # 1. Build the prompt
    prompt = (f"{data.scene}"
#        f"product '{data.product_name}', features include {', '.join(data.features)}."
#        "scene: \"{scene}\"."
#        "Important No Text, Follow scene, Studio lighting, advertise shot, realistic, DSLR, 4K"
    )

    # 2. Generate base image
    for attempt in range(3):
        try:
            prompt = trim_prompt(prompt)
            print('Prompt:', prompt)
            base_image = pipe(prompt, guidance_scale=7.5, num_inference_steps=40).images[0]
            break
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1)

    # 3. Refine image
    final_image = refiner(
        prompt=prompt,
        image=base_image,
        strength=0.3,
        guidance_scale=7.5,
        num_inference_steps=20
    ).images[0]

    # 4. Add brand/CTA overlay
    branded_image = add_overlay(final_image, data.brand_text, data.product_name, data.cta_text)

    # 5. Save and return download URL
    filename = f"{uuid.uuid4()}.png"
    file_path = os.path.join(IMAGES_DIR, filename)
    branded_image.save(file_path)
    
    # Track creation time and schedule cleanup
    image_timestamps[filename] = time.time()
    schedule_cleanup(file_path, filename)

    return {
        "filename": filename,
        "download_url": f"/download/{filename}",
        "expires_in_minutes": 10
    }

@app.get("/download/{filename}")
def download_image(filename: str):
    """Download endpoint for generated images"""
    file_path = os.path.join(IMAGES_DIR, filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found or has expired")
    
    # Check if image has expired (more than 10 minutes old)
    if filename in image_timestamps:
        creation_time = image_timestamps[filename]
        if time.time() - creation_time > 600:  # 10 minutes
            # Clean up expired image
            try:
                os.remove(file_path)
                del image_timestamps[filename]
            except:
                pass
            raise HTTPException(status_code=404, detail="Image has expired")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/status/{filename}")
def check_image_status(filename: str):
    """Check if an image is still available"""
    file_path = os.path.join(IMAGES_DIR, filename)
    
    if not os.path.exists(file_path):
        return {"status": "not_found", "message": "Image not found or has expired"}
    
    if filename in image_timestamps:
        creation_time = image_timestamps[filename]
        elapsed_time = time.time() - creation_time
        remaining_time = max(0, 600 - elapsed_time)  # 10 minutes = 600 seconds
        
        if remaining_time > 0:
            return {
                "status": "available",
                "remaining_minutes": round(remaining_time / 60, 1),
                "download_url": f"/download/{filename}"
            }
        else:
            return {"status": "expired", "message": "Image has expired"}
    
    return {"status": "unknown", "message": "Image status unknown"}

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "image-generator"}

