export default (instance) => ({
  getUsers(page) {
    return instance({
      method: "GET",
      url: `/users/`,
      params: { page, size: 10 },
    }).then((response) => response.data);
  },
  getUserById(id) {
    return instance({
      method: "GET",
      url: `/users/find/${id}`,
    }).then((response) => response.data);
  },
  searchUsers(term, page) {
    return instance({
      method: "GET",
      url: `/users/search/paginated`,
      params: { name: term, page, size: 10 },
    }).then((response) => response.data);
  },
  addUserByTg(id) {
    return instance({
      method: "POST",
      url: `/users/`,
      data: { tg_id: id },
    }).then((response) => response.data);
  },
  updateUser(id, data) {
    return instance({
      method: "PATCH",
      url: `/users/${id}`,
      data,
    }).then((response) => response.data);
  },
  deleteUser(id) {
    return instance({
      method: "DELETE",
      url: `/users/${id}`,
    }).then((response) => response.data);
  },
  blockUser(id) {
    return instance({
      method: "PATCH",
      url: `/users/${id}/block`,
    }).then((response) => response.data);
  },
  unblockUser(id) {
    return instance({
      method: "PATCH",
      url: `/users/${id}/unblock`,
    }).then((response) => response.data);
  },
});
