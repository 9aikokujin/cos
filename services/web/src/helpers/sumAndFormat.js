export function sumAndFormat(numbers) {
  const sum = numbers.reduce((total, num) => total + (Number(num) || 0), 0);

  if (sum <= 999) return sum.toString();

  if (sum <= 999999) {
    const thousands = sum / 1000;
    return thousands % 1 === 0
      ? `${thousands} тыс`
      : `${thousands.toFixed(1).replace(".0", "").replace(".", ",")}тыс`;
  }

  const millions = sum / 1000000;
  return millions % 1 === 0
    ? `${millions} млн`
    : `${millions.toFixed(1).replace(".0", "").replace(".", ",")}млн`;
}
