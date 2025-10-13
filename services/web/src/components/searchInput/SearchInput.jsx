import { useState, useEffect, useRef } from "react";
import classNames from "classnames";

import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";

import "./SearchInput.css";

const SearchInput = ({
  value,
  setValue,
  placeholder = "Поиск",
  onSearch,
  alwaysExpanded = false,
  width = "400px",
}) => {
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

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && onSearch) {
      onSearch(value);
    }
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
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyPress={handleKeyPress}
        autoFocus={expanded || alwaysExpanded}
      />
    </div>
  );
};

export default SearchInput;
