import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";

import closeIcon from "@/assets/img/icons/close.svg";

import "./BottomModal.css";

const BottomModal = ({ id, isOpen, onClose, children, heightContent, subMenu }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsVisible(true);
      document.body.style.overflow = "hidden";
    } else {
      setIsVisible(false);
      document.body.style.overflow = "auto";
    }

    return () => {
      document.body.style.overflow = "auto";
    };
  }, [isOpen]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 300); // Ждём окончания анимации (300ms)
  };

  if (!isOpen && !isVisible) return null;

  return ReactDOM.createPortal(
    <div
      className={`modal-overlay ${!isVisible ? "modal-overlay--closing" : ""}`}
      onClick={handleClose}
    >
      <div
        id={id}
        className={`modal-content _flex_center ${!isVisible ? "modal-content--closing" : ""}`}
        onClick={(e) => e.stopPropagation()}
        style={{
          height: heightContent,
        }}
      >
        {!subMenu && (
          <div className="modal-header">
            <button onClick={handleClose} className="modal-close-button">
              <img src={closeIcon} alt="" />
            </button>
          </div>
        )}
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.getElementById("modal-root")
  );
};

export default BottomModal;
