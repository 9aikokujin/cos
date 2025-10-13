import React from "react";

import { useModalStore } from "@/app/store/modal/store";
import { useNotificationStore } from "@/app/store/notification/store";
import { useFiltersModalStore } from "@/app/store/filterModal/store";

import { ModalBottom, ModalCenter } from "@/shared/ui/modal/Modal";
import { FiltersModal } from "../filter/components/filterModal/FilterModal";

import "./AppModal.css";

const AppModals = () => {
  const { modal, isOpen, closeModal } = useModalStore();
  const { isOpen: filtersOpen, filters, closeFiltersModal, onApply } = useFiltersModalStore();
  const { notification, isOpen: notifOpen, closeNotification } = useNotificationStore();

  return (
    <>
      <ModalBottom isOpen={isOpen} onClose={closeModal} height={modal?.height}>
        {modal?.content}
      </ModalBottom>

      <ModalCenter isOpen={notifOpen} onClose={closeNotification}>
        {notification}
      </ModalCenter>

      <FiltersModal
        isOpen={filtersOpen}
        onClose={closeFiltersModal}
        filters={filters}
        onApply={onApply}
      />
    </>
  );
};

export default AppModals;
