import "./CustomInput.css";

const CustomInput = ({ placeholder, classname, value, onChange, onFocus, error }) => {
  return (
    <>
      <div className="input__field ">
        {error && <span className="error_message">{error.message || error}</span>}
        <input
          value={value}
          onChange={onChange}
          className={`custom__input ${error && "_error"} ${classname}`}
          type="text"
          placeholder={placeholder}
          onFocus={onFocus}
        />
      </div>
    </>
  );
};

export default CustomInput;
