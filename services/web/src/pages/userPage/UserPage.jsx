import API from "@/app/api";
import { useSearch } from "@/hooks/useSearch";
import { useUsersStore } from "@/app/store/entity/store";

import UserList from "@/components/usersList/UserList";
import Filter from "@/components/filter/Filter";
import SearchInput from "@/components/searchInput/SearchInput";

const fetchUsers = async (term) => {
  const response = await API.user.searchUsers(term, 1);
  return response;
};

const UserPage = () => {
  const { searchTerm, setSearchTerm } = useSearch(useUsersStore, fetchUsers, "users");
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <SearchInput value={searchTerm} setValue={setSearchTerm} />
      </div>
      <UserList />
    </div>
  );
};

export default UserPage;
