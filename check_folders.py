import os

def print_directory_structure(startpath, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', 'venv', 'env'}
    
    for root, dirs, files in os.walk(startpath):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = '│   ' * level
        print(f'{indent}├── {os.path.basename(root)}/')
        subindent = '│   ' * (level + 1)
        for f in files:
            print(f'{subindent}├── {f}')

# Usage example:
# Save this script as 'show_structure.py' in your project root
# Then run: python show_structure.py

if __name__ == "__main__":
    current_directory = os.getcwd()  # Gets current working directory
    print("\nProject Structure:")
    print_directory_structure(current_directory)