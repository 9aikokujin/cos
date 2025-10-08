import dayjs from "dayjs";

export const getPeriodDates = (period) => {
  const today = dayjs();
  let startDate;

  switch (period) {
    case "today":
      startDate = today;
      break;
    case "week":
      startDate = today.subtract(1, "week");
      break;
    case "month":
      startDate = today.subtract(1, "month");
      break;
    case "3months":
      startDate = today.subtract(3, "months");
      break;
    case "6months":
      startDate = today.subtract(6, "months");
      break;
    case "year":
      startDate = today.subtract(1, "year");
      break;
    default:
      return null;
  }

  return {
    start: startDate,
    end: today,
  };
};
