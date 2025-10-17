import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import classNames from "classnames";

import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import { debounce } from "@/shared/utils/debounce";

import "./SearchInput.css";

const SearchInput = ({ store, placeholder = "Поиск", alwaysExpanded = false, width = "400px" }) => {
  const setTerm = store((s) => s.setTerm);
  const [inputValue, setInputValue] = useState("");
  const [expanded, setExpanded] = useState(false);
  const wrapperRef = useRef(null);

  // Закрытие при клике вне компонента
  useEffect(() => {
    if (alwaysExpanded) return;

    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setExpanded(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const debouncedSetTerm = useMemo(() => debounce((value) => setTerm(value), 400), [setTerm]);

  // на размонтировании/смене setTerm — отменяем таймер
  useEffect(() => {
    return () => {
      if (debouncedSetTerm.cancel) debouncedSetTerm.cancel();
    };
  }, [debouncedSetTerm]);

  const handleChange = (e) => {
    const value = e.target.value;
    setInputValue(value);
    debouncedSetTerm(value); // <-- без .current !
  };

  return (
    <div
      ref={wrapperRef}
      className={classNames("search_wrapper", { expanded: expanded || alwaysExpanded })}
      onClick={() => !alwaysExpanded && setExpanded(true)}
      style={{ width: alwaysExpanded && width }}
    >
      <ComponentIcon name="search" className="search_icon" />
      <input
        type="text"
        className="search_input"
        placeholder={placeholder}
        value={inputValue}
        onChange={handleChange}
        autoFocus={expanded || alwaysExpanded}
      />
    </div>
  );
};

export default SearchInput;
