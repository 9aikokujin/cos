// import React, { useState, useEffect } from "react";
// import { AnimatePresence, motion } from "framer-motion";

// import { ModalBottom } from "@/shared/ui/modal/Modal";
// import { Button } from "@/shared/ui/button/Button";
// import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";

// import "./FilterModal.css";

// const slideVariants = {
//   enter: (custom) => ({
//     x: "100%",
//     opacity: 0,
//     width: "100%",
//     height: "100%",
//   }),
//   center: {
//     x: "0%",
//     opacity: 1,
//     width: "100%",
//     height: "100%",
//   },
//   exit: (custom) => ({
//     x: "-100%",
//     opacity: 0,
//     width: "100%",
//     height: "100%",
//   }),
// };

// export const FiltersModal = ({ isOpen, onClose, filters = [] }) => {
//   // const [stack, setStack] = useState([]); // стек экранов
//   // const [prevIndex, setPrevIndex] = useState(0);

//   // useEffect(() => {
//   //   if (!isOpen) {
//   //     setStack([]);
//   //     setPrevIndex(0);
//   //   }
//   // }, [isOpen]);

//   // const currentIndex = stack.length;

//   // const openNext = (screen) => {
//   //   setPrevIndex(currentIndex);
//   //   setStack((prev) => [...prev, screen]);
//   // };

//   // const goBack = () => {
//   //   setPrevIndex(currentIndex);
//   //   setStack((prev) => prev.slice(0, -1));
//   // };

//   // const handleSelectFilter = (value) => {
//   //   console.log("Выбран фильтр:", value);
//   //   // TODO: сохранить в store
//   // };

//   // const handleApply = () => {
//   //   console.log("Применить фильтры");
//   //   onClose();
//   // };

//   // const handleClearFilter = () => {
//   //   console.log("фильтр очищен");
//   //   onClose();
//   // };

//   // const currentScreen = stack[stack.length - 1];

//   // // Первый экран — список фильтров
//   // const handleOpenFilter = (filter) => {
//   //   if (filter.subComponent) {
//   //     openNext({
//   //       id: filter.id,
//   //       title: filter.title,
//   //       component: filter.component,
//   //     });
//   //   } else {
//   //     openNext({
//   //       id: filter.id,
//   //       title: filter.title,
//   //       component: filter.component,
//   //     });
//   //   }
//   // };

//   const {
//     isOpen,
//     close,
//     filters,
//     stack,
//     push,
//     pop,
//     footer,
//   } = useFilterModalStore();

//   const direction = 1;

//   const ActiveFilter =
//     stack.length === 0
//       ? () => <FilterList filters={filters} onSelect={push} />
//       : stack[stack.length - 1].component;

//   const activeFilterProps =
//     stack.length === 0
//       ? {}
//       : { filter: stack[stack.length - 1], onBack: pop };

//   return (
//     <ModalBottom isOpen={isOpen} onClose={onClose} height="auto" backgroundColor="#F4EEE9">
//       <div className="filters-modal">
//         <AnimatePresence mode="wait" initial={false}>
//           {/* Экран списка фильтров */}
//           {stack.length === 0 && (
//             <MotionScreen key="filter-list" custom={currentIndex - prevIndex}>
//               <FilterListScreen filters={filters} onSelect={handleOpenFilter} />
//             </MotionScreen>
//           )}

//           {/* Экран выбранного фильтра */}
//           {stack.length >= 1 && currentScreen && (
//             <MotionScreen key={currentScreen.id} custom={currentIndex - prevIndex}>
//               <button className="back_btn" onClick={goBack}>
//                 <ComponentIcon name={"go-back"} />
//               </button>
//               <currentScreen.component
//                 onBack={goBack}
//                 onNext={openNext}
//                 onSelect={handleSelectFilter}
//               />
//             </MotionScreen>
//           )}
//         </AnimatePresence>

//         <div className="filter_apply_container _flex_col_center">
//           <Button className="_orange _filter_btn" onClick={handleApply}>
//             Применить
//           </Button>
//           <Button className="_grey _filter_btn" onClick={handleClearFilter}>
//             Очистить
//           </Button>
//         </div>
//       </div>
//     </ModalBottom>
//   );
// };

// // --------------------- Motion обертка ---------------------
// const MotionScreen = ({ children, custom }) => (
//   <motion.div
//     custom={custom}
//     variants={slideVariants}
//     initial="enter"
//     animate="center"
//     exit="exit"
//     transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
//     className="screen"
//   >
//     {children}
//   </motion.div>
// );

// // --------------------- Экран списка фильтров ---------------------
// const FilterListScreen = ({ filters, onSelect }) => (
//   <div className="filter_list">
//     <h2>Фильтр</h2>
//     <ul className="_flex_col_center" style={{ gap: 14 }}>
//       {filters.map((f) => (
//         <li key={f.id} className="filter_item" onClick={() => onSelect(f)}>
//           {f.title}
//         </li>
//       ))}
//     </ul>
//   </div>
// );

import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { useFiltersModalStore } from "@/app/store/filterModal/store";

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

  // const direction = 1;
  const [direction, setDirection] = useState(1);
  const handlePush = (filter) => {
    setDirection(1);
    push(filter);
  };

  const handlePop = () => {
    setDirection(-1);
    pop();
  };

  const ActiveView =
    stack.length === 0
      ? () => <FilterList filters={filters} onSelect={handlePush} />
      : stack[stack.length - 1].component;

  const activeProps =
    stack.length === 0 ? {} : { filter: stack[stack.length - 1], onBack: handlePop };
  // const ActiveFilter =
  //   stack.length === 0
  //     ? () => <FilterList filters={filters} onSelect={push} />
  //     : stack[stack.length - 1].component;

  // const activeFilterProps =
  //   stack.length === 0 ? {} : { filter: stack[stack.length - 1], onBack: pop };

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
            <Button className="_grey _filter_btn" onClick={close}>
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
