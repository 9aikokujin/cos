import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import classNames from "classnames";
import "./Button.css";

export const Button = ({ children, className, onClick, type, disabled, style }) => {
  return (
    <button className={classNames("button", className)} onClick={onClick} type={type} disabled={disabled} style={style}>
      {children}
    </button>
  );
};

export const ButtonIcon = ({ name, className, onClick, type, disabled, style }) => {
  return (
    <button className={classNames("button_icon", className)} onClick={onClick} type={type} disabled={disabled} style={style}>
      <ComponentIcon name={name} />
    </button>
  );
};
