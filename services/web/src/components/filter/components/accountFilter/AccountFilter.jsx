import { useEffect, useState } from "react";

import SearchInput from "@/components/searchInput/SearchInput";
import { useFiltersModalStore } from "@/app/store/filterModal/store";
import { useMultiSelectFilter } from "../../../../hooks/useMultiSelectFilter";

const mockiAccount = [
  { name: "Захарова Алефтина Олеговна", id: "1" },
  { name: "Захарова Алефтина Олеговна", id: "2" },
  { name: "Захарова Алефтина Олеговна", id: "3" },
  { name: "Петров Иван Сергеевич", id: "4" },
  { name: "Соколова Анна Владимировна", id: "5" },
  { name: "Захарова Алефтина Олеговна", id: "6" },
  { name: "Петров Иван Сергеевич", id: "7" },
  { name: "Захарова Алефтина Олеговна", id: "8" },
  { name: "Соколова Анна Владимировна", id: "9" },
  { name: "Захарова Алефтина Олеговна", id: "10" },
  { name: "Петров Иван Сергеевич", id: "11" },
  { name: "Соколова Анна Владимировна", id: "12" },
  { name: "Петров Иван Сергеевич", id: "13" },
  { name: "Захарова Алефтина Олеговна", id: "14" },
];

const AccountFilter = () => {
  const [searchValue, setSearchValue] = useState("");
  const filteredAccounts = mockiAccount.filter((acc) =>
    acc.name.toLowerCase().includes(searchValue.toLowerCase())
  );
  const { selected, toggleSelect } = useMultiSelectFilter("Применить", (tags) => {
    console.log("Выбранные соцсети:", tags);
  });
  return (
    <div className="account_filter _flex_col_center">
      <h2>Аккаунты</h2>
      <div className="account_search">
        <SearchInput placeholder="Поиск" alwaysExpanded onSearch={setSearchValue} width={"100%"} />
      </div>
      <ul className="account_list _flex_col_center">
        {filteredAccounts.map((account) => (
          <li
            key={account.id}
            className={`filter_item _flex_center ${selected.includes(account.id) ? "_active" : ""}`}
            onClick={() => toggleSelect(account.id)}
          >
            <p className="_name">{account.name}</p>
          </li>
        ))}
        {filteredAccounts.length === 0 && <p className="empty_result">Ничего не найдено</p>}
      </ul>
    </div>
  );
};

export default AccountFilter;
