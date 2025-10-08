import dayjs from "dayjs";
import isBetween from "dayjs/plugin/isBetween";
import { useMemo, useState } from "react";

import { useFilter } from "@/store/FilterAnalitic/main";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import CustomButton from "@/ui/button/CustomButton";
import {
  daysOfTheWeek,
  getCurrentMonthDays,
  getDaysAmountInMonth,
  getNextMonthDays,
  getPrevMonthDays,
  getWeekNumber,
  months,
} from "./utils/utils";

import "./DatePicker.css";

dayjs.extend(isBetween);

export const DatePicker = ({ value, onChange, close }) => {
  const [panelYear, setPanelYear] = useState(() => value.year());
  const [panelMonth, setPanelMonth] = useState(() => value.month());
  const [selectedRange, setSelectedRange] = useState({ start: null, end: null });
  const {
    actions: { setRangeFilter },
  } = useFilter();

  const [year, month, date] = useMemo(() => {
    const currentYear = value.year();
    const currentDay = value.date();
    const currentMonth = value.month();

    return [currentYear, currentMonth, currentDay];
  }, [value]);

  const dateCells = useMemo(() => {
    const daysInMonth = getDaysAmountInMonth(panelYear, panelMonth);

    const currentMonthDays = getCurrentMonthDays(panelYear, panelMonth, daysInMonth);

    const prevMonthDays = getPrevMonthDays(panelYear, panelMonth);
    const nextMonthDays = getNextMonthDays(panelYear, panelMonth);

    return [...prevMonthDays, ...currentMonthDays, ...nextMonthDays];
  }, [panelYear, panelMonth]);

  const today = dayjs();

  const onDateSelect = (item) => {
    const selectedDate = dayjs(new Date(item.year, item.month, item.date));

    if (!selectedRange.start || (selectedRange.start && selectedRange.end)) {
      setSelectedRange({ start: selectedDate, end: null });
    } else if (selectedDate.isBefore(selectedRange.start)) {
      setSelectedRange({ start: selectedDate, end: selectedRange.start });
    } else {
      setSelectedRange({ ...selectedRange, end: selectedDate });
    }

    onChange(selectedDate);
  };

  const isDateInRange = (date) => {
    if (!selectedRange.start) return false;
    if (!selectedRange.end) return date.isSame(selectedRange.start, "day");

    return date.isBetween(selectedRange.start, selectedRange.end, "day", "[]");
  };

  const prevMonth = () => {
    if (panelMonth === 0) {
      setPanelMonth(11);
      setPanelYear(panelYear - 1);
    } else {
      setPanelMonth(panelMonth - 1);
    }
  };
  const nextMonth = () => {
    if (panelMonth === 11) {
      setPanelMonth(0);
      setPanelYear(panelYear + 1);
    } else {
      setPanelMonth(panelMonth + 1);
    }
  };

  const handleSelectRange = () => {
    setRangeFilter(selectedRange);
    close();
  };

  return (
    <div>
      <div className="_flex_jc_between">
        <button onClick={prevMonth}>
          <ComponentIcon name={"arrow-left"} />
        </button>
        <p className="calendar__month">{months[panelMonth]}</p>
        <button onClick={nextMonth}>
          <ComponentIcon name={"arrow-right"} />
        </button>
      </div>
      <div
        style={{
          width: 300,
          height: 300,
          display: "grid",
          gridTemplateColumns: "repeat(8,1fr)",
          gridTemplateRows: `auto repeat(${Math.ceil(dateCells.length / 7)}, 1fr)`,
          alignItems: "center",
          justifyItems: "center",
          marginBottom: "30px",
        }}
      >
        <div
          className="calendar__header"
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          01
        </div>
        {daysOfTheWeek.map((item) => {
          return (
            <div
              key={item}
              className="calendar__header"
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              {item}
            </div>
          );
        })}
        {Array.from({ length: Math.ceil(dateCells.length / 7) }).map((_, weekIndex) => {
          const weekStartDate = dateCells[weekIndex * 7]?.date;

          const weekNumber = getWeekNumber(new Date(panelYear, panelMonth, weekStartDate || 1));

          return (
            <>
              <div
                key={weekIndex}
                className="calendar__week_number"
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                {weekNumber}
              </div>

              {dateCells.slice(weekIndex * 7, (weekIndex + 1) * 7).map((cell, dayIndex) => {
                const cellDate = dayjs(new Date(cell.year, cell.month, cell.date));
                const isToday = cellDate.isSame(today, "day");
                const isInRange = isDateInRange(cellDate);

                const dayClasses = [
                  "calendar__day",
                  dayIndex === 5 || dayIndex === 6 ? "_week_end" : "",
                  !cell.isCurrentMonth ? "_another_month" : "",
                  isToday ? "_active" : "",
                  isInRange ? "_active" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <div
                    className={dayClasses}
                    style={{
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      cursor: "pointer",
                    }}
                    onClick={() => onDateSelect(cell)}
                  >
                    {cell.date}
                  </div>
                );
              })}
            </>
          );
        })}
      </div>
      <CustomButton onClick={handleSelectRange}>Выбрать</CustomButton>
    </div>
  );
};
