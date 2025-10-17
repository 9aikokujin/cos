export function formatNumber(value) {
  if (value === null || value === undefined || isNaN(value)) return "0";
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function combineNameFields(user, priority = ["last_name", "first_name", "fullname"]) {
  const nameParts = priority
    .filter((field) => user[field] && user[field].trim())
    .map((field) => user[field].trim());

  return nameParts.join(" ");
}

export function formatNameToInitials(user) {
  if (!user) return "User";
  const { fullname, first_name, last_name } = user;

  if (last_name && last_name.trim()) {
    return formatFromFullName(last_name.trim());
  }

  if (first_name && first_name.trim() && fullname && fullname.trim()) {
    return formatFromFirstLastName(first_name.trim(), fullname.trim());
  }

  if (fullname && fullname.trim()) {
    return fullname.trim();
  }

  if (first_name && first_name.trim()) {
    return first_name.trim();
  }

  return "User";
}

function formatFromFullName(fullname) {
  const parts = fullname.split(" ").filter((part) => part.trim());

  if (parts.length === 1) {
    return parts[0];
  }

  const lastName = parts[parts.length - 1];
  const firstNames = parts.slice(0, parts.length - 1);

  const initials = firstNames.map((name) => name.charAt(0) + ".").join("");

  return `${lastName} ${initials}`.trim();
}

function formatFromFirstLastName(firstName, lastName) {
  const initials = firstName
    .split(" ")
    .map((part) => part.charAt(0) + ".")
    .join("");

  return `${lastName} ${initials}`.trim();
}
