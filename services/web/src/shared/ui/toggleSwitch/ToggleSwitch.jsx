import classNames from "classnames";
import "./ToggleSwitch.css";

const ToggleSwitch = ({ label, checked, onChange, disabled }) => {
  return (
    <label className={classNames("toggle_wrapper", { disabled })}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="toggle_input"
      />
      <span className="toggle_slider" />
      {label && <span className="toggle_label">{label}</span>}
    </label>
  );
};

export default ToggleSwitch;
