"""
File operation tools for agents.

These tools handle basic file operations like reading, writing, and checking files.
"""
from crewai.tools import tool
from typing import Dict, Any
from pathlib import Path
from utilities import logger


@tool("Read File")
def read_file_tool(file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Read contents of a text file.
    
    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)
        
    Returns:
        Dictionary with file contents or error
    """
    logger.info(f"Reading file: {file_path}")
    
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        content = path.read_text(encoding=encoding)
        
        return {
            "success": True,
            "file_path": file_path,
            "content": content,
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Write File")
def write_file_tool(file_path: str, content: str, encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Write content to a text file.
    
    Args:
        file_path: Path to the file to write
        content: Content to write
        encoding: File encoding (default: utf-8)
        
    Returns:
        Dictionary with success status
    """
    logger.info(f"Writing to file: {file_path}")
    
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        
        return {
            "success": True,
            "file_path": file_path,
            "bytes_written": len(content.encode(encoding))
        }
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Check File Exists")
def check_file_exists_tool(file_path: str) -> Dict[str, Any]:
    """
    Check if a file or directory exists.
    
    Args:
        file_path: Path to check
        
    Returns:
        Dictionary with existence status and file type
    """
    logger.info(f"Checking if exists: {file_path}")
    
    path = Path(file_path)
    exists = path.exists()
    
    result = {
        "exists": exists,
        "path": file_path
    }
    
    if exists:
        result["is_file"] = path.is_file()
        result["is_directory"] = path.is_dir()
        result["size"] = path.stat().st_size if path.is_file() else None
    
    return result


@tool("Get File Info")
def get_file_info_tool(file_path: str) -> Dict[str, Any]:
    """
    Get detailed information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information including size, timestamps, etc.
    """
    logger.info(f"Getting info for: {file_path}")
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        stat = path.stat()
        
        return {
            "success": True,
            "path": file_path,
            "name": path.name,
            "extension": path.suffix,
            "size": stat.st_size,
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime
        }
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        return {
            "success": False,
            "error": str(e)
        }
