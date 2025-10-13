export const debounce = (fn, delay = 400) => {
    let timer;
  
    const debounced = (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        fn(...args);
      }, delay);
    };
  
    debounced.cancel = () => {
      clearTimeout(timer);
    };
  
    return debounced;
  };
  