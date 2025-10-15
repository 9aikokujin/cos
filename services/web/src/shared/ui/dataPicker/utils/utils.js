export const VISIBLE_CELLS_AMOUNT = 35;

export const months = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];

export const daysOfTheWeek = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

export const getDaysAmountInMonth = (year, month) => {
  const nextMonthDate = new Date(year, month + 1, 1);
  nextMonthDate.setMinutes(-1);
  return nextMonthDate.getDate();
};

export const getCurrentMonthDays = (year, month, numberOfDays) => {
  const dateCells = [];

  for (let i = 1; i <= numberOfDays; i++) {
    dateCells.push({
      year,
      month,
      date: i,
      isCurrentMonth: true,
    });
  }

  return dateCells;
};

export const getPrevMonthDays = (year, month) => {
  const currentMonthFirstDay = new Date(year, month, 1);
  const prevMonthCellsAmount = (currentMonthFirstDay.getDay() || 7) - 1;

  const daysAmountInPrevMonth = getDaysAmountInMonth(year, month - 1);

  const dateCells = [];

  const [cellYear, cellMonth] = month === 0 ? [year - 1, 11] : [year, month - 1];

  for (let i = prevMonthCellsAmount - 1; i >= 0; i--) {
    dateCells.push({
      year: cellYear,
      month: cellMonth,
      date: daysAmountInPrevMonth - i,
      isCurrentMonth: false,
    });
  }

  return dateCells;
};

export const getNextMonthDays = (year, month) => {
  const currentMonthFirstDay = new Date(year, month, 1);
  const prevMonthCellsAmount = (currentMonthFirstDay.getDay() || 7) - 1;

  const daysAmount = getDaysAmountInMonth(year, month);

  const nextMonthDays = VISIBLE_CELLS_AMOUNT - daysAmount - prevMonthCellsAmount;

  const [cellYear, cellMonth] = month === 11 ? [year + 1, 0] : [year, month + 1];

  const dateCells = [];

  for (let i = 1; i <= nextMonthDays; i++) {
    dateCells.push({
      year: cellYear,
      month: cellMonth,
      date: i,
      isCurrentMonth: false,
    });
  }

  return dateCells;
};

export const getInputValueFromDate = (value) => {
  return value.format("DD-MM-YYYY");
};

export const getWeekNumber = (date) => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
  const yearStart = new Date(d.getFullYear(), 0, 1);
  return Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
};
