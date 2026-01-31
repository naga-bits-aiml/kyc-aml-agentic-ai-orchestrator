"""
Image processing tools for document conversion.
"""
import sys
from pathlib import Path

# Add parent directory to path when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, Any, List
from crewai.tools import tool
from utilities import logger
from PIL import Image


@tool("convert_png_to_jpeg")
def convert_png_to_jpeg_tool(folder_path: str) -> Dict[str, Any]:
    """
    Convert all PNG images in a folder to JPEG format.
    
    Args:
        folder_path: Path to folder containing PNG images
        
    Returns:
        Dictionary with conversion results:
        {
            "success": true/false,
            "converted": ["file1.jpg", "file2.jpg"],
            "failed": ["file3.png"],
            "message": "Converted X of Y files"
        }
    """
    logger.info(f"Converting PNG images to JPEG in: {folder_path}")
    
    try:
        folder = Path(folder_path).expanduser().resolve()
        
        if not folder.exists():
            return {
                "success": False,
                "error": f"Folder not found: {folder_path}"
            }
        
        if not folder.is_dir():
            return {
                "success": False,
                "error": f"Not a folder: {folder_path}"
            }
        
        # Find all PNG files
        png_files = list(folder.glob("*.png")) + list(folder.glob("*.PNG"))
        
        if not png_files:
            return {
                "success": True,
                "converted": [],
                "failed": [],
                "message": "No PNG files found in folder"
            }
        
        converted = []
        failed = []
        
        for png_path in png_files:
            try:
                # Open PNG image
                with Image.open(png_path) as img:
                    # Convert RGBA to RGB if needed (JPEG doesn't support alpha)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Create white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Create JPEG path
                    jpeg_path = png_path.with_suffix('.jpg')
                    
                    # Save as JPEG with good quality
                    img.save(jpeg_path, 'JPEG', quality=95)
                    
                    converted.append(str(jpeg_path.name))
                    logger.info(f"Converted: {png_path.name} -> {jpeg_path.name}")
                    
            except Exception as e:
                failed.append(str(png_path.name))
                logger.error(f"Failed to convert {png_path.name}: {e}")
        
        return {
            "success": True,
            "converted": converted,
            "failed": failed,
            "message": f"Converted {len(converted)} of {len(png_files)} PNG files to JPEG"
        }
        
    except Exception as e:
        logger.error(f"Error converting images: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@tool("convert_single_png_to_jpeg")
def convert_single_png_to_jpeg_tool(png_file_path: str) -> Dict[str, Any]:
    """
    Convert a single PNG image to JPEG format.
    
    Args:
        png_file_path: Path to PNG file
        
    Returns:
        Dictionary with conversion result
    """
    try:
        png_path = Path(png_file_path).expanduser().resolve()
        
        if not png_path.exists():
            return {"success": False, "error": f"File not found: {png_file_path}"}
        
        if png_path.suffix.lower() != '.png':
            return {"success": False, "error": f"Not a PNG file: {png_file_path}"}
        
        with Image.open(png_path) as img:
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            jpeg_path = png_path.with_suffix('.jpg')
            img.save(jpeg_path, 'JPEG', quality=95)
            
            logger.info(f"Converted: {png_path.name} -> {jpeg_path.name}")
            
            return {
                "success": True,
                "input": str(png_path),
                "output": str(jpeg_path),
                "message": f"Converted {png_path.name} to {jpeg_path.name}"
            }
            
    except Exception as e:
        logger.error(f"Error converting image: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python image_tools.py <folder_path>")
        print("  Converts all PNG images in folder to JPEG")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    print(f"Converting PNG images in: {folder_path}")
    
    result = convert_png_to_jpeg_tool.run(folder_path)
    print(json.dumps(result, indent=2))
