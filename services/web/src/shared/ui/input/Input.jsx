import classNames from "classnames";

import "./Input.css";

const Input = ({
  type,
  placeholder,
  value,
  className,
  error,
  onChange,
  disabled,
  style,
  ...props
}) => {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      style={style}
      className={classNames("input", { _error: !!error }, className)}
      {...props}
    />
  );
};

export const Textarea = ({
  type,
  placeholder,
  value,
  className,
  error,
  onChange,
  disabled,
  style,
  ...props
}) => {
  return (
    <textarea
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      style={style}
      className={classNames("textarea input", { _error: !!error }, className)}
      {...props}
    />
  );
};

export default Input;
