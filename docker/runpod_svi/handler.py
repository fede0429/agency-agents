import runpod
import os
import boto3
import uuid

# --- SVI Inference Logic Loader ---
# Replace this with your actual SVI model loading when deploying heavy.
# from svi_inference_logic import run_svi_film 

# ---- Environment Variables Injected by RunPod Secrets ----
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")  # e.g. https://<account_id>.r2.cloudflarestorage.com
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "svi-assets") 

def upload_to_r2(local_path: str, filename: str) -> str:
    """真实上传到 Cloudflare R2 网盘，并返回一小时内有效的预签名下载链接"""
    
    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_ENDPOINT_URL]):
        raise ValueError("Missing S3 credentials in environment. Check RunPod Secrets.")
        
    print(f"Uploading {filename} to Cloudflare R2 bucket: {S3_BUCKET_NAME}...")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name="auto" # Default for Cloudflare R2
    )
    
    # 执行上传
    s3_client.upload_file(local_path, S3_BUCKET_NAME, filename)
    
    # 生成一个 1 小时有效期的下载直链，让客户端能快速拿到文件
    url = s3_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': S3_BUCKET_NAME, 'Key': filename},
        ExpiresIn=3600
    )
    return url

def run_inference(prompt: str, image_url: str):
    """
    包装核心的 Wan 2.1 14B SVI 逻辑
    """
    # 真实情况在这调用 torch 生成帧序列并输出到本地 .mp4
    # 这里做个占位文件便于我们把流程跑通
    output_filename = f"svi_gen_{uuid.uuid4().hex[:8]}.mp4"
    dummy_local_path = f"/tmp/{output_filename}"
    
    # 生成一个假的占位视频文件
    with open(dummy_local_path, "wb") as f:
        f.write(b"video stream byte data...")
        
    return dummy_local_path

def handler(job):
    job_input = job['input']
    prompt = job_input.get('prompt', '')
    image_url = job_input.get('image_url')
    
    if not prompt:
        return {"error": "Prompt cannot be empty"}
        
    try:
        # 1. 显卡满载生成视频
        local_video_path = run_inference(prompt, image_url)
        
        # 2. 注入刚刚准备好的 Cloudflare R2 凭据推向网盘
        video_filename = os.path.basename(local_video_path)
        access_url = upload_to_r2(local_video_path, video_filename)
        
        # 3. 垃圾回收释放容器空间，避免爆仓
        if os.path.exists(local_video_path):
            os.remove(local_video_path)
            
        # 返回签发好的公开 URL，让主进程下载
        return {"video_url": access_url}
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": str(e)}

if __name__ == "__main__":
    # 启动等待 RunPod 调用
    runpod.serverless.start({"handler": handler})
