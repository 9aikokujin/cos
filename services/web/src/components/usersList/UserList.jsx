import API from "@/app/api";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useUsersStore } from "@/app/store/entity/store";

import Loader from "@/components/loader/Loader";
import UserItem from "./components/UserItem";

import "./UserList.css";

const fetchUsers = async (page) => {
  const response = await API.user.getUsers(page);
  return response;
};

const UserList = () => {
  const { items, isLoading, hasMore, lastItemRef } = useInfiniteScroll(
    useUsersStore,
    fetchUsers,
    "users"
  );
  return (
    <div className="_flex_col_center" style={{ gap: 20, overflow: "auto", paddingBottom: 20 }}>
      {items.map((item, i) => (
        <UserItem key={item.id} ref={i === items.length - 1 ? lastItemRef : null} user={item} />
      ))}
      {isLoading && <Loader />}
    </div>
  );
};

export default UserList;
