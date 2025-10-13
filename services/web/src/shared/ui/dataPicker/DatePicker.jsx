// import dayjs from "dayjs";
// import isBetween from "dayjs/plugin/isBetween";
// import { useMemo, useState } from "react";

// import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
// // import CustomButton from "@/shared/ui/button/CustomButton";
// import {
//   daysOfTheWeek,
//   getCurrentMonthDays,
//   getDaysAmountInMonth,
//   getNextMonthDays,
//   getPrevMonthDays,
//   getWeekNumber,
//   months,
// } from "./utils/utils";

// import "./DatePicker.css";

// dayjs.extend(isBetween);

// export const DatePicker = ({ value, onChange, close, mode = "range", minDate = null }) => {
//   const [panelYear, setPanelYear] = useState(() => value.year());
//   const [panelMonth, setPanelMonth] = useState(() => value.month());
//   const [selectedRange, setSelectedRange] = useState({ start: null, end: null });
//   // const {
//   //   actions: { setRangeFilter },
//   // } = useFilter();

//   const [year, month, date] = useMemo(() => {
//     const currentYear = value.year();
//     const currentDay = value.date();
//     const currentMonth = value.month();

//     return [currentYear, currentMonth, currentDay];
//   }, [value]);

//   const dateCells = useMemo(() => {
//     const daysInMonth = getDaysAmountInMonth(panelYear, panelMonth);

//     const currentMonthDays = getCurrentMonthDays(panelYear, panelMonth, daysInMonth);

//     const prevMonthDays = getPrevMonthDays(panelYear, panelMonth);
//     const nextMonthDays = getNextMonthDays(panelYear, panelMonth);

//     return [...prevMonthDays, ...currentMonthDays, ...nextMonthDays];
//   }, [panelYear, panelMonth]);

//   const today = dayjs();

//   const onDateSelect = (item) => {
//     const selectedDate = dayjs(new Date(item.year, item.month, item.date));

//     if (mode === "single" && minDate && selectedDate.isBefore(minDate, "day")) {
//       return; // Не позволяем выбрать дату, если она раньше minDate
//     }
//     if (mode === "single") {
//       // Режим выбора одной даты
//       onChange(selectedDate);
//       if (close) close();
//     } else {
//       // Режим выбора периода (старая логика)
//       if (!selectedRange.start || (selectedRange.start && selectedRange.end)) {
//         setSelectedRange({ start: selectedDate, end: null });
//       } else if (selectedDate.isBefore(selectedRange.start)) {
//         setSelectedRange({ start: selectedDate, end: selectedRange.start });
//       } else {
//         setSelectedRange({ ...selectedRange, end: selectedDate });
//       }

//       if (mode === "range") {
//         onChange(selectedDate);
//       }
//     }
//   };

//   const isDateInRange = (date) => {
//     if (mode === "single") return date.isSame(value, "day");

//     if (!selectedRange.start) return false;
//     if (!selectedRange.end) return date.isSame(selectedRange.start, "day");

//     return date.isBetween(selectedRange.start, selectedRange.end, "day", "[]");
//   };

//   const isDateSelectable = (date) => {
//     if (mode !== "single") return true;
//     if (!minDate) return !date.isAfter(today, "day");// Ограничение только для режима single
//     if (!minDate) return true; // Если minDate не передан, все даты доступны

//     return !date.isBefore(minDate, "day") && !date.isAfter(today, "day");
//   };

//   const prevMonth = () => {
//     if (panelMonth === 0) {
//       setPanelMonth(11);
//       setPanelYear(panelYear - 1);
//     } else {
//       setPanelMonth(panelMonth - 1);
//     }
//   };
//   const nextMonth = () => {
//     if (panelMonth === 11) {
//       setPanelMonth(0);
//       setPanelYear(panelYear + 1);
//     } else {
//       setPanelMonth(panelMonth + 1);
//     }
//   };

//   const handleSelectRange = () => {
//     if (mode === "range" && selectedRange.start && selectedRange.end) {
//       // setRangeFilter(selectedRange);
//       if (close) close();
//     }
//   };

//   const isRangeSelectionComplete = mode === "range" && selectedRange.start && selectedRange.end;

//   return (
//     <div>
//       <div className="_flex_jc_between">
//         <button onClick={prevMonth}>
//           <ComponentIcon name={"arrow-left"} />
//         </button>
//         <p className="calendar__month">{months[panelMonth]}</p>
//         <button onClick={nextMonth}>
//           <ComponentIcon name={"arrow-right"} />
//         </button>
//       </div>
//       <div
//         style={{
//           width: 300,
//           height: 300,
//           display: "grid",
//           gridTemplateColumns: "repeat(7,1fr)",
//           gridTemplateRows: `auto repeat(${Math.ceil(dateCells.length / 7)}, 1fr)`,
//           alignItems: "center",
//           justifyItems: "center",
//           marginBottom: "30px",
//         }}
//       >
//         {daysOfTheWeek.map((item) => {
//           return (
//             <div
//               key={item}
//               className="calendar__header"
//               style={{
//                 display: "flex",
//                 justifyContent: "center",
//                 alignItems: "center",
//               }}
//             >
//               {item}
//             </div>
//           );
//         })}
//         {Array.from({ length: Math.ceil(dateCells.length / 7) }).map((_, weekIndex) => {
//           return (
//             <>
//               {dateCells.slice(weekIndex * 7, (weekIndex + 1) * 7).map((cell, dayIndex) => {
//                 const cellDate = dayjs(new Date(cell.year, cell.month, cell.date));
//                 const isToday = cellDate.isSame(today, "day");
//                 const isInRange = isDateInRange(cellDate);
//                 const isSelectable = isDateSelectable(cellDate);

//                 const dayClasses = [
//                   "calendar__day",
//                   dayIndex === 5 || dayIndex === 6 ? "_week_end" : "",
//                   !cell.isCurrentMonth ? "_another_month" : "",
//                   isToday ? "_active" : "",
//                   isInRange ? "_active" : "",
//                   !isSelectable ? "_disabled" : "",
//                 ]
//                   .filter(Boolean)
//                   .join(" ");
//                 return (
//                   <div
//                     className={dayClasses}
//                     style={{
//                       display: "flex",
//                       justifyContent: "center",
//                       alignItems: "center",
//                       cursor: isSelectable ? "pointer" : "not-allowed",
//                     }}
//                     onClick={() => isSelectable && onDateSelect(cell)}
//                   >
//                     {cell.date}
//                   </div>
//                 );
//               })}
//             </>
//           );
//         })}
//       </div>
//       {/* {mode === "range" && <CustomButton onClick={handleSelectRange}>Выбрать</CustomButton>} */}
//     </div>
//   );
// };

import dayjs from "dayjs";
import isBetween from "dayjs/plugin/isBetween";
import { useMemo, useState, useEffect, useCallback } from "react";

import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import { useFiltersModalStore } from "@/app/store/filterModal/store";

import {
  daysOfTheWeek,
  getCurrentMonthDays,
  getDaysAmountInMonth,
  getNextMonthDays,
  getPrevMonthDays,
  months,
} from "./utils/utils";

import "./DatePicker.css";

dayjs.extend(isBetween);

export const DatePicker = ({ mode = "range", initialValue }) => {
  const { setFooter, close } = useFiltersModalStore();

  const today = dayjs();
  const [panelYear, setPanelYear] = useState(today.year());
  const [panelMonth, setPanelMonth] = useState(today.month());
  const [selectedRange, setSelectedRange] = useState(initialValue || { start: null, end: null });

  // Формирование всех дат месяца
  const dateCells = useMemo(() => {
    const daysInMonth = getDaysAmountInMonth(panelYear, panelMonth);
    return [
      ...getPrevMonthDays(panelYear, panelMonth),
      ...getCurrentMonthDays(panelYear, panelMonth, daysInMonth),
      ...getNextMonthDays(panelYear, panelMonth),
    ];
  }, [panelYear, panelMonth]);

  const handleDateClick = (item) => {
    const selectedDate = dayjs(new Date(item.year, item.month, item.date));

    setSelectedRange((prev) => {
      if (!prev.start || (prev.start && prev.end)) {
        return { start: selectedDate, end: null };
      }
      if (selectedDate.isBefore(prev.start)) {
        return { start: selectedDate, end: prev.start };
      }
      return { ...prev, end: selectedDate };
    });
  };

  const isDateInRange = (date) => {
    const { start, end } = selectedRange;
    if (!start) return false;
    if (!end) return date.isSame(start, "day");
    return date.isBetween(start, end, "day", "[]");
  };

  const prevMonth = () => {
    setPanelMonth((prev) => (prev === 0 ? 11 : prev - 1));
    if (panelMonth === 0) setPanelYear((y) => y - 1);
  };
  const nextMonth = () => {
    setPanelMonth((prev) => (prev === 11 ? 0 : prev + 1));
    if (panelMonth === 11) setPanelYear((y) => y + 1);
  };

  // Устанавливаем футер модалки (Применить / Очистить)
  useEffect(() => {
    setFooter({
      text: "Применить",
      visible: true,
      onClick: () => {
        if (selectedRange.start && selectedRange.end) {
          console.log("✅ Диапазон выбран:", selectedRange);
          close();
        }
      },
    });
  }, [selectedRange]);

  return (
    <div className="date_picker _flex_col_center" style={{ gap: 10 }}>
      <div className="_flex_sb" style={{ width: 345 }}>
        <button onClick={prevMonth}>
          <ComponentIcon name={"arrow-left"} />
        </button>
        <p className="calendar__month">
          {months[panelMonth]}
        </p>
        <button onClick={nextMonth}>
          <ComponentIcon name={"arrow-right"} />
        </button>
      </div>

      <div
        className="calendar_grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
        }}
      >
        {daysOfTheWeek.map((day) => (
          <div key={day} className="calendar__header">
            {day}
          </div>
        ))}

        {dateCells.map((cell, index) => {
          const cellDate = dayjs(new Date(cell.year, cell.month, cell.date));
          const isCurrent = cell.isCurrentMonth;
          const isActive = isDateInRange(cellDate);

          return (
            <div
              key={index}
              onClick={() => handleDateClick(cell)}
              className={`calendar__day ${isActive ? "_active" : ""} ${
                !isCurrent ? "_another_month" : ""
              }`}
            >
              {cell.date}
            </div>
          );
        })}
      </div>
    </div>
  );
};
