import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { useFiltersModalStore } from "@/app/store/filterModal/store";
import { useFilterStore } from "@/app/store/filter/store";

import { ModalBottom } from "@/shared/ui/modal/Modal";
import { Button } from "@/shared/ui/button/Button";
import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";

import "./FilterModal.css";

const slideVariants = {
  enter: (direction) => ({
    x: direction > 0 ? "100%" : "-100%",
    opacity: 0,
  }),
  center: { x: 0, opacity: 1 },
  exit: (direction) => ({
    x: direction < 0 ? "100%" : "-100%",
    opacity: 0,
  }),
};

export const FiltersModal = () => {
  const { isOpen, close, filters, stack, push, pop, footer } = useFiltersModalStore();
  const resetAllFilters = useFilterStore((s) => s.resetFilter);

  const [direction, setDirection] = useState(1);
  const handlePush = (filter) => {
    setDirection(1);
    push(filter);
  };

  const handlePop = () => {
    setDirection(-1);
    pop();
  };

  const hansleResetFilter = () => {
    if (footer.resetFilter) {
      footer.resetFilter();
    } else {
      resetAllFilters();
    }
    close();
  };

  const ActiveView =
    stack.length === 0
      ? () => <FilterList filters={filters} onSelect={handlePush} />
      : stack[stack.length - 1].component;

  const activeProps =
    stack.length === 0 ? {} : { filter: stack[stack.length - 1], onBack: handlePop };

  return (
    <ModalBottom isOpen={isOpen} onClose={close} height="auto">
      <div className="filters_modal" style={{ overflow: "hidden" }}>
        <AnimatePresence mode="wait" initial={false} custom={direction}>
          <motion.div
            key={stack.length}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.3 }}
            className="screen"
          >
            {stack.length >= 1 && (
              <button className="back_btn" onClick={handlePop}>
                <ComponentIcon name={"go-back"} />
              </button>
            )}
            <ActiveView {...activeProps} />
          </motion.div>
        </AnimatePresence>

        {footer.visible && (
          <div className="filter_apply_container _flex_col_center">
            <Button className="_orange _filter_btn" onClick={footer.onClick || close}>
              {footer.text || "Применить"}
            </Button>
            <Button className="_grey _filter_btn" onClick={hansleResetFilter}>
              Очистить
            </Button>
          </div>
        )}
      </div>
    </ModalBottom>
  );
};

const FilterList = ({ filters, onSelect }) => (
  <div className="filter_list">
    <h2>Фильтры</h2>
    <ul className="_flex_col_center" style={{ gap: 14 }}>
      {filters.map((f) => (
        <li key={f.id} onClick={() => onSelect(f)} className="filter_item">
          {f.title}
        </li>
      ))}
    </ul>
  </div>
);
