import { useRef, useState } from "react";

import CustomButton from "@/ui/button/CustomButton";

import searchIcon from "@/assets/img/icons/search.svg";

import "./AnimatedInput.css";

export const AnimatedSearch = ({ onSearch, value }) => {
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef(null);

  const toggleSearch = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      onSearch("");
    }
  };

  return (
    <div className={`search-container ${isOpen ? "open" : ""}`}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Поиск..."
        className="search-input"
      />
      <CustomButton onClick={toggleSearch} classname={"_search_btn"}>
        <img src={searchIcon} alt="" />
      </CustomButton>
    </div>
  );
};
