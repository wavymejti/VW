"""
Main entry point for showing the functionality in this project.
"""

from algorithms import binary_search, bubble_sort


def example_algorithms():
    """
    Example code to showcase binary search and bubble sort algorithms.
    """
    # Demonstrate bubble sort
    unsorted_list = [64, 34, 25, 12, 22, 11, 90]
    print(f"Unsorted list: {unsorted_list}")
    
    sorted_list = bubble_sort(unsorted_list)
    print(f"Sorted list using Bubble Sort: {sorted_list}")
    
    # Demonstrate binary search
    target_value = 25
    print(f"\nSearching for {target_value} in the sorted list...")
    
    index = binary_search(sorted_list, target_value)
    if index != -1:
        print(f"Target {target_value} found at index: {index}")
    else:
        print(f"Target {target_value} not found in the list.")


def main():
    """
    Main execution method.
    """
    print("--- Algorithm Examples ---\n")
    example_algorithms()


if __name__ == "__main__":
    main()
