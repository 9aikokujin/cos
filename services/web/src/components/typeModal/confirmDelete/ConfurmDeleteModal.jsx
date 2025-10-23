import { Button } from "@/shared/ui/button/Button";

const ConfurmDeleteModal = ({ title, description, onConfirm, onCancel, btnTitle }) => {
  return (
    <div className="modal_content" id="confusmDeleteModal">
      <h2 className="modal_title">{title}</h2>
      <div className="modal_form _flex_col">
        <p className="modal_text">{description}</p>
        <Button className={"_orange modal_btn"} onClick={onConfirm}>
          {btnTitle}
        </Button>
        <Button className={"_grey modal_btn"} onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </div>
  );
};

export default ConfurmDeleteModal;
