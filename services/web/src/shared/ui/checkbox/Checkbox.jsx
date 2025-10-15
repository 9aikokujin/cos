import classNames from "classnames";

import "./Checkbox.css";

const Checkbox = ({ label, checked, onChange, disabled }) => {
  return (
    <label className={classNames("checkbox_wrapper", { disabled })}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="checkbox_input"
      />
      <span className="checkbox_custom">
        <svg
          width="13"
          height="9"
          viewBox="0 0 13 9"
          className={classNames("checkbox_icon", { checked })}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M11.753 1L5.3891 7.364C4.9986 7.7545 4.3654 7.7545 3.97487 7.364L1.5 4.8891"
            stroke="#FEC178"
            stroke-width="1.25"
            stroke-linecap="round"
          />
        </svg>
      </span>
      {label && <span className="checkbox_label">{label}</span>}
    </label>
  );
};

export default Checkbox;
