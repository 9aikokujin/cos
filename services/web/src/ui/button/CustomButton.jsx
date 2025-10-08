import "./CustomButtom.css";

const CustomButton = ({ children, classname, type, form, disabled, onClick }) => {
  return (
    <>
      <button
        className={`custom__button ${classname}`}
        onClick={onClick}
        type={type}
        form={form}
        disabled={disabled}
      >
        {children}
      </button>
    </>
  );
};

export default CustomButton;
