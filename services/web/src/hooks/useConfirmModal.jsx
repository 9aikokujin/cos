import { useCallback } from "react";

import ConfurmDeleteModal from "@/components/typeModal/confirmDelete/ConfurmDeleteModal";
import { useModalStore } from "@/app/store/modal/store";

export const useConfirmModal = () => {
  const { openModal, closeModal } = useModalStore();

  const confirmAction = useCallback(
    ({ title, description, onConfirm, btnTitle }) => {
      openModal(
        <ConfurmDeleteModal
          title={title}
          description={description}
          btnTitle={btnTitle}
          onConfirm={() => {
            onConfirm?.();
            closeModal();
          }}
          onCancel={closeModal}
        />
      );
    },
    [openModal, closeModal]
  );

  return { confirmAction };
};
