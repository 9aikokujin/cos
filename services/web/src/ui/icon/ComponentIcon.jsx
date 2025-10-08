import { useState, useEffect } from "react";
import classNames from "classnames";


export const ComponentIcon = ({ className, name, size, style, onClick }) => {
  const [Icon, setIcon] = useState(null);
  const modifiers = {
    [`component-icon--${size}`]: size,
  };

  useEffect(() => {
    import(`./icons/${name}.svg?react`).then((module) => {
      setIcon(() => module.default);
    });
  }, [name]);

  if (!Icon) return null; // Или лоадер

  return (
    <Icon
      fill="currentColor"
      className={`component-icon ${classNames(modifiers)} ${className ?? ""}`}
      style={style}
      onClick={onClick}
    />
  );
};
