import { useState, useEffect } from "react";

export const useInput = (initialValue = "", delay = 0) => {
  const [value, setValue] = useState(initialValue);
  const [debouncedValue, setDebouncedValue] = useState(initialValue);
  const [error, setError] = useState("");

  useEffect(() => {
    if (delay <= 0) {
      setDebouncedValue(value);
      return;
    }

    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  const onChange = (e) => {
    setValue(e.target.value);
    if (error) setError("");
  };

  const clear = () => {
    setValue("");
    setDebouncedValue("");
  };

  return {
    value,
    debouncedValue,
    setDebouncedValue,
    onChange,
    clear,
    error,
    setError,
    setValue,
    isEmpty: !value.trim(),
    isDirty: value !== initialValue,
  };
};
