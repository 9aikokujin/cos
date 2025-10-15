import { useCallback } from "react";

import ConfurmDeleteModal from "@/components/typeModal/confirmDelete/ConfurmDeleteModal";
import { useModalStore } from "@/app/store/modal/store";

export const useConfirmModal = () => {
  const { openModal, closeModal } = useModalStore();

  const confirmAction = useCallback(
    ({ title, description, onConfirm }) => {
      openModal(
        <ConfurmDeleteModal
          title={title}
          description={description}
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
