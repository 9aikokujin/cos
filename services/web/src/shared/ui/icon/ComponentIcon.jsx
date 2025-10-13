import { useState, useEffect } from "react";
import classNames from "classnames";

import "./ComponentIcon.css";


export const ComponentIcon = ({
  name,
  size,
  className,
  style,
  onClick,
  lazy = true,
  loader = true,
}) => {
  const [Icon, setIcon] = useState(null);
  const [loading, setLoading] = useState(true);

  const modifiers = {
    [`component-icon--${size}`]: size,
  };

  useEffect(() => {
    let cancelled = false;

    async function loadIcon() {
      try {
        setLoading(true);
        const module = await import(`./icons/${name}.svg?react`);
        if (!cancelled) {
          setIcon(() => module.default);
        }
      } catch (e) {
        console.warn(`⚠️ Icon "${name}" not found`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (lazy) loadIcon();

    return () => {
      cancelled = true;
    };
  }, [name, lazy]);

  if (loading && loader) {
    return (
      <div
        className={classNames(
          "component-icon__loader",
          modifiers,
          className
        )}
        style={{
          ...style,
        }}
      />
    );
  }

  if (!Icon) return null;

  return (
    <Icon
      fill="currentColor"
      className={classNames("component-icon", modifiers, className)}
      style={style}
      onClick={onClick}
    />
  );
};
