from fastapi import FastAPI
from pydantic import BaseModel
from diffusers import (
    StableDiffusionXLPipeline,
    StableDiffusionXLImg2ImgPipeline,
    EulerAncestralDiscreteScheduler
)
from PIL import Image, ImageDraw, ImageFont
import torch, uuid, os
from transformers import CLIPTokenizer

app = FastAPI()
clip_tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")

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

    # 5. Save and return path
    path = f"/tmp/{uuid.uuid4()}.png"
    branded_image.save(path)

    return {"url": path}

