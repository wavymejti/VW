"""
This module contains implementations of common algorithms.

Algorithms included:
- Binary Search
- Bubble Sort
"""

def binary_search(arr: list, target) -> int:
    """
    Perform a binary search on a sorted list to find the target element.

    Args:
        arr (list): A sorted list of elements.
        target: The element to search for.

    Returns:
        int: The index of the target if found, otherwise -1.
    """
    left = 0
    right = len(arr) - 1

    while left <= right:
        mid = (left + right) // 2
        
        # Check if target is present at mid
        if arr[mid] == target:
            return mid
        
        # If target is greater, ignore left half
        elif arr[mid] < target:
            left = mid + 1
            
        # If target is smaller, ignore right half
        else:
            right = mid - 1
            
    # Target is not present in the list
    return -1


def bubble_sort(arr: list) -> list:
    """
    Sort a list of elements using the bubble sort algorithm.

    Args:
        arr (list): The list of elements to sort.

    Returns:
        list: A new sorted list.
    """
    # Create a copy to avoid mutating the original list
    sorted_arr = arr.copy()
    n = len(sorted_arr)
    
    # Traverse through all array elements
    for i in range(n):
        swapped = False
        
        # Last i elements are already in place
        for j in range(0, n - i - 1):
            
            # Swap if the element found is greater than the next element
            if sorted_arr[j] > sorted_arr[j + 1]:
                sorted_arr[j], sorted_arr[j + 1] = sorted_arr[j + 1], sorted_arr[j]
                swapped = True
                
        # If no two elements were swapped by inner loop, then break
        if not swapped:
            break
            
    return sorted_arr
