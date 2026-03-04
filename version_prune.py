#!/usr/bin/python3

import os
import argparse
import sys
import time
import threading
import shutil
from pathlib import Path

def find_target_folders_with_versions(path, target_folders):
    """
    Scan for target folders and recursively find version directories within them.
    
    Args:
        path (str): Root path to scan
        target_folders (set): Set of folder names to look for version folders in
    
    Returns:
        dict: Dictionary mapping folder paths to their version directories
    """
    folders_with_versions = {}
    
    def scan_for_versions(folder_path, depth=0, max_depth=10):
        """
        Recursively scan within a target folder for all paths containing version directories.
        Returns a list of tuples: [(path, [version_folders]), ...]
        """
        if depth > max_depth:
            return []
        
        version_dirs = []
        results = []
        
        try:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    # If it's a version folder, add it to current level
                    if item.startswith("v0"):
                        version_dirs.append(item)
                    else:
                        # Also recurse into non-version subdirectories to find more version folders
                        sub_results = scan_for_versions(item_path, depth + 1, max_depth)
                        results.extend(sub_results)
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not access {folder_path}: {e}")
        
        # If we found version folders at this level, add to results
        # This happens regardless of whether we found subdirectories with versions
        if version_dirs:
            results.append((folder_path, version_dirs))
        
        return results
    
    try:
        for root, dirs, files in os.walk(path):
            root_name = os.path.basename(root)
            
            # Check if current folder is one of our target folders
            if root_name in target_folders:
                # Recursively scan within this target folder for all version directories
                results = scan_for_versions(root)
                for version_path, version_dirs in results:
                    folders_with_versions[version_path] = sorted(version_dirs)
                
                # Don't walk into subdirectories of target folders
                # since we're handling them separately
                dirs.clear()
    except (OSError, PermissionError) as e:
        print(f"Warning: Error scanning directory {path}: {e}")
    
    return folders_with_versions

def human_size(fsize, units=[' bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']):
    """Convert bytes to human readable format."""
    return "{:.2f}{}".format(float(fsize), units[0]) if fsize < 1024 else human_size(fsize / 1024, units[1:])

def folder_size(folder_path):
    """Calculate total size of a folder and its contents."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for file in filenames:
                file_path = os.path.join(dirpath, file)
                if not os.path.islink(file_path):
                    total_size += os.path.getsize(file_path)
    except (OSError, IOError) as e:
        print(f"Warning: Could not calculate size for {folder_path}: {e}")
    
    return total_size



def main():
    parser = argparse.ArgumentParser(
        description="Prune old version folders from specified directory types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python version_prune.py --path /path/to/project --threshold 5
  python version_prune.py -p /path/to/project -t 3 --folders renders comps test
  python version_prune.py -p /path/to/project -t 2 --dry --folders renders
        """
    )
    
    parser.add_argument("--path", "-p", help="The path to start crawling from.", type=str, required=True)
    parser.add_argument("--threshold", "-t", metavar='N', 
                       help="The number of versions to keep.", type=int, required=True)
    parser.add_argument("--dry", "-d", help="Dry-run to see what would be removed.", 
                       action="store_true")
    parser.add_argument("--folders", "-f", nargs='+', 
                       default=['renders'],
                       help="List of folder types to search for version folders in (default: renders)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist.")
        sys.exit(1)
    
    if args.threshold < 1:
        print("Error: Threshold must be at least 1.")
        sys.exit(1)
    
    # Convert folder list to set for faster lookup
    target_folders = set(args.folders)
    
    print("\n\n---------- Version Prune ----------\n")
    
    if args.dry:
        print("Attention: DRY RUN\n")
    
    print(f"Searching for version folders in: {', '.join(sorted(target_folders))}")
    print("This may take a while.\n")
    
    # Use a simple approach - store result in a list that can be modified by thread
    result = [None]
    animation_stop = threading.Event()
    
    def scrape_target():
        result[0] = find_target_folders_with_versions(args.path, target_folders)
        animation_stop.set()
    
    def animate_loading():
        chars = "/—\\|"
        i = 0
        while not animation_stop.is_set():
            sys.stdout.write('\r' + 'Scanning... ' + chars[i % len(chars)])
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    
    # Start both threads
    scrape_process = threading.Thread(target=scrape_target)
    animation_thread = threading.Thread(target=animate_loading)
    
    scrape_process.daemon = True
    animation_thread.daemon = True
    
    scrape_process.start()
    animation_thread.start()
    
    # Wait for scraping to complete
    scrape_process.join()
    animation_stop.set()
    animation_thread.join(timeout=0.5)  # Give animation thread time to stop
    
    # Clear the loading animation
    sys.stdout.write('\r' + 'Scanning complete!' + ' ' * 10 + '\n')
    sys.stdout.flush()
    
    folders_with_versions = result[0]
    
    if not folders_with_versions:
        print("No version folders found matching the criteria.")
        return
    
    print(f"Found {len(folders_with_versions)} folders containing version directories.\n")
    
    # Process each folder containing version directories
    total_remove = 0
    remove_list = []
    
    for folder, versions in sorted(folders_with_versions.items()):
        
        if not versions:
            continue
        
        num_versions = len(versions)
        
        # Check if we need to prune
        if num_versions > args.threshold:
            versions_to_remove = num_versions - args.threshold
            
            print("--------------------------------------------------------------------------")
            print(f"Root folder:          {folder}")
            print(f"Total versions:       {num_versions}")
            print(f"Versions to keep:     {args.threshold}")
            print(f"Versions to remove:   {versions_to_remove}")
            print("Found versions:")
            
            for version in versions:
                print(f"                      {version}")
            
            print("\n               >>> Removal List <<<")
            
            # Remove oldest versions (first in sorted list)
            prune_list = versions[:versions_to_remove]
            
            for prune in prune_list:
                remove_dir = os.path.join(folder, prune)
                dir_size = folder_size(remove_dir)
                remove_list.append(remove_dir)
                total_remove += dir_size
                
                print(f"\nWould Remove: {prune}")
                print(f"        Path: {remove_dir}")
                print(f"        Size: {human_size(dir_size)}")
    
    if not remove_list:
        print("No folders need to be removed based on the threshold.")
        return
    
    print("--------------------------------------------------------------------------")
    print(f"\n\nTotal size to be deleted: {human_size(total_remove)}")
    print(f"Total folders to be removed: {len(remove_list)}")
    
    # Execute removal if not a dry run
    if not args.dry:
        while True:
            answer = input("\nDo you want to remove all the folders listed for removal? (y/n): ").lower().strip()
            
            if answer == 'y':
                print("\nRemoving folders...")
                success_count = 0
                error_count = 0
                
                for remove_dir in remove_list:
                    print(f"Removing: {remove_dir}")
                    
                    try:
                        shutil.rmtree(remove_dir, ignore_errors=False)
                        print("Success")
                        success_count += 1
                    except OSError as error:
                        print(f"Error: {error}")
                        error_count += 1
                
                print(f"\nRemoval complete: {success_count} succeeded, {error_count} failed")
                break
                
            elif answer == 'n':
                print("Exiting without removing folders.")
                break
            else:
                print("Please enter 'y' or 'n'")
    else:
        print("\nDry-run complete. No folders were removed.")

if __name__ == "__main__":
    main()