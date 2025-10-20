import { useMemo, useState, useEffect } from "react";
import dayjs from "dayjs";
import isBetween from "dayjs/plugin/isBetween";

import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import { useFiltersModalStore } from "@/app/store/filterModal/store";
import { useFilterStore } from "@/app/store/filter/store";

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
  const setDateFrom = useFilterStore((state) => state.setFilterDateFrom);
  const setDateTo = useFilterStore((state) => state.setFilterDateTo);

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

  useEffect(() => {
    setFooter({
      text: "Применить",
      visible: true,
      onClick: () => {
        if (selectedRange.start && selectedRange.end) {
          setDateFrom(selectedRange.start.format("YYYY-MM-DD"));
          setDateTo(selectedRange.end.format("YYYY-MM-DD"));
          close();
        }
      },
    });
  }, [selectedRange]);

  return (
    <div className="date_picker _flex_col_center" style={{ gap: 10, marginBottom: 41 }}>
      <div className="_flex_sb" style={{ width: 345 }}>
        <button onClick={prevMonth}>
          <ComponentIcon name={"arrow-left"} />
        </button>
        <p className="calendar__month">{months[panelMonth]}</p>
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
        {/* Заголовки дней недели */}
        {daysOfTheWeek.map((day, index) => {
          const isWeekend = index === 5 || index === 6;
          return (
            <div key={day} className={`calendar__header ${isWeekend ? "_week_end" : ""}`}>
              {day}
            </div>
          );
        })}

        {/* Сами даты */}
        {dateCells.map((cell, index) => {
          const cellDate = dayjs(new Date(cell.year, cell.month, cell.date));
          const isCurrent = cell.isCurrentMonth;
          const isActive = isDateInRange(cellDate);
          const isWeekend = cellDate.day() === 0 || cellDate.day() === 6;

          return (
            <div
              key={index}
              onClick={() => handleDateClick(cell)}
              className={`calendar__day 
                ${isActive ? "_active" : ""} 
                ${!isCurrent ? "_another_month" : ""} 
                ${isWeekend ? "_week_end" : ""}`}
            >
              {cell.date}
            </div>
          );
        })}
      </div>
    </div>
  );
};
