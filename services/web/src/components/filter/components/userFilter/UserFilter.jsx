import API from "@/app/api";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useMultiSelectFilter } from "@/hooks/useMultiSelectFilter";
import { useUsersStore } from "@/app/store/entity/store";
import { useFilterStore } from "@/app/store/filter/store";

import { combineNameFields } from "@/shared/utils/formatString";

import SearchInput from "@/components/searchInput/SearchInput";

const fetchUsers = async (page, term) => {
  if (!term) {
    const response = await API.user.getUsers(page);
    return response;
  } else {
    const response = await API.user.searchUsers(term, page);
    return response;
  }
};

const UserFilter = () => {
  const setUserId = useFilterStore((s) => s.setFilterUserId);

  const { items, isLoading, lastItemRef } = useInfiniteScroll(useUsersStore, fetchUsers, "users");
  const { selected, toggleSelect } = useMultiSelectFilter("Применить", (user) => {
    setUserId(user);
  }, true);
  return (
    <div className="account_filter _flex_col_center">
      <h2>Пользователи</h2>
      <div className="account_search">
        <SearchInput store={useUsersStore} placeholder="Поиск" alwaysExpanded width={"100%"} />
      </div>
      <ul className="account_list _flex_col_center">
        {items.map((user, i) => (
          <li
            key={user.id}
            ref={user.id === items.length - 1 ? lastItemRef : null}
            className={`filter_item _flex_center ${selected.includes(user.id) ? "_active" : ""}`}
            onClick={() => toggleSelect(user.id)}
          >
            <p className="_name">{combineNameFields(user)}</p>
          </li>
        ))}
        {items.length === 0 && <p className="empty_result">Ничего не найдено</p>}
      </ul>
    </div>
  );
};

export default UserFilter;
