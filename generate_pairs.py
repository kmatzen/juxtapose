#!/usr/bin/env python3
"""
Helper script to generate all pairwise comparisons for multiple methods.

Usage:
    python generate_pairs.py > image_pairs.txt

Edit the PROMPTS and METHODS below, then run this script to generate
a properly formatted image_pairs.txt file with all pairwise combinations.
"""

from itertools import combinations

# Define your methods
METHODS = {
    "Method-A": "https://example.com/method_a",  # Base URL or prefix for Method-A images
    "Method-B": "https://example.com/method_b",  # Base URL or prefix for Method-B images
    "Method-C": "https://example.com/method_c",  # Base URL or prefix for Method-C images
}

# Define your prompts
PROMPTS = [
    "A serene mountain landscape at sunset",
    "A futuristic city with flying cars",
    "A cat wearing sunglasses on a beach",
    # Add more prompts here...
]

def generate_image_url(method_base_url, prompt_index):
    """
    Generate the image URL for a method and prompt.
    Customize this function based on how your images are named/organized.
    """
    return f"{method_base_url}/prompt_{prompt_index:03d}.jpg"

def main():
    print("# Image Pairs Configuration")
    print("# Generated with all pairwise method combinations")
    print("# Format: prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url")
    print()
    
    # Generate all pairwise combinations
    method_names = list(METHODS.keys())
    pairs = list(combinations(method_names, 2))
    
    print(f"# Total methods: {len(method_names)}")
    print(f"# Pairwise comparisons per prompt: {len(pairs)}")
    print(f"# Prompts: {len(PROMPTS)}")
    print(f"# Total comparisons: {len(pairs) * len(PROMPTS)}")
    print()
    
    for prompt_idx, prompt in enumerate(PROMPTS):
        if prompt_idx > 0:
            print()  # Blank line between prompt groups
        
        print(f"# Prompt {prompt_idx + 1}: {prompt}")
        
        for method_a, method_b in pairs:
            # Generate image URLs
            image_a_url = generate_image_url(METHODS[method_a], prompt_idx)
            image_b_url = generate_image_url(METHODS[method_b], prompt_idx)
            
            # Output tab-separated line
            print(f"{prompt}\t{method_a}\t{method_b}\t{image_a_url}\t{image_b_url}")

if __name__ == "__main__":
    main()

