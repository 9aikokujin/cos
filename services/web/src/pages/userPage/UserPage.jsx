import { useUsersStore } from "@/app/store/entity/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import UserList from "@/components/usersList/UserList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const UserPage = () => {
  useResetFiltersOnLeave()
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput store={useUsersStore} />
      </div>
      <UserList />
    </div>
  );
};

export default UserPage;
