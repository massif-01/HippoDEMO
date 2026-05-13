/**
 * Creates a debounced version of a function using requestAnimationFrame
 * This is optimized for UI updates during streaming
 */
export function rafDebounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number = 0
): (...args: Parameters<T>) => void {
  let rafId: number | null = null;
  let timeoutId: NodeJS.Timeout | null = null;
  
  return (...args: Parameters<T>) => {
    // Cancel any pending updates
    if (rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    
    // Schedule the update
    if (delay > 0) {
      timeoutId = setTimeout(() => {
        if (typeof requestAnimationFrame !== 'undefined') {
          rafId = requestAnimationFrame(() => {
            fn(...args);
            rafId = null;
          });
        } else {
          fn(...args);
        }
      }, delay);
    } else {
      if (typeof requestAnimationFrame !== 'undefined') {
        rafId = requestAnimationFrame(() => {
          fn(...args);
          rafId = null;
        });
      } else {
        fn(...args);
      }
    }
  };
}

/**
 * Throttle function calls to a maximum frequency
 * Useful for high-frequency updates like streaming
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  let lastArgs: Parameters<T> | null = null;
  
  return (...args: Parameters<T>) => {
    lastArgs = args;
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
        if (lastArgs) {
          fn(...lastArgs);
          lastArgs = null;
        }
      }, limit);
    }
  };
}

