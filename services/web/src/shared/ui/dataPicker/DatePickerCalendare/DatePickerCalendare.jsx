import dayjs from "dayjs";
import { useState, useMemo } from "react";
import { getDaysAmountInMonth, getCurrentMonthDays, getPrevMonthDays, getNextMonthDays, months, daysOfTheWeek } from "../../utils/utils";

export const DatePickerCalendare = ({
    value,
    onChange,
    min,
    max,
  }) => {
    const [panelYear, setPanelYear] = useState(() => value.year());
    const [panelMonth, setPanelMonth] = useState(() => value.month());
  
    const [year, month, date] = useMemo(() => {
      const currentYear = value.year();
      const currentDay = value.date();
      const currentMonth = value.month();
  
      return [currentYear, currentMonth, currentDay];
    }, [value]);
  
    const dateCells = useMemo(() => {
      const daysInMonth = getDaysAmountInMonth(panelYear, panelMonth);
  
      const currentMonthDays = getCurrentMonthDays(
        panelYear,
        panelMonth,
        daysInMonth
      );
  
      const prevMonthDays = getPrevMonthDays(panelYear, panelMonth);
      const nextMonthDays = getNextMonthDays(panelYear, panelMonth);
  
      return [...prevMonthDays, ...currentMonthDays, ...nextMonthDays];
    }, [panelYear, panelMonth]);
  
    const onDateSelect = (item) => {
      onChange(dayjs(new Date(item.year, item.month, item.date)));
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
  
    return (
      <div>
        <div>
          <button onClick={prevMonth}>prev month</button>
          <button>{months[panelMonth]}</button>
          <button>{panelYear}</button>
          <button onClick={nextMonth}>next month</button>
        </div>
        <div
          style={{
            width: 300,
            height: 300,
            display: "grid",
            gridTemplateColumns: "repeat(7,1fr)",
            gridTemplateRows: "repeat(7, 1fr)",
          }}
        >
          {daysOfTheWeek.map((item) => {
            return (
              <div
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
          {dateCells.map((cell) => {
            return (
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  border: "1px solid #000",
                  cursor: "pointer",
                }}
                onClick={() => onDateSelect(cell)}
              >
                {cell.date}
              </div>
            );
          })}
        </div>
      </div>
    );
  };
  