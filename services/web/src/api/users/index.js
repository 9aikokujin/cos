export default (instance) => ({
  getAll({ page, size }) {
    return instance({
      method: "GET",
      url: "/users/",
      params: {
        page,
        size,
      },
    }).then((response) => response.data);
  },

  searchUser({ token, name, page, size }) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: "users/search/paginated",
      params: {
        name,
        page,
        size,
      },
    }).then((response) => response.data);
  },

  getAllChanels({ page, size, token, id, type, link, name_channel }) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: "channels/all",
      params: {
        user_id: id,
        name_channel,
        link,
        type,
        page,
        size,
      },
    }).then((response) => response.data);
  },

  getMe(token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: "users/me",
    }).then((response) => response.data);
  },

  getUserById({ id, token }) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: `users/find/${id}`,
    }).then((response) => response.data);
  },

  createChannel({ id, token, data }) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "POST",
      url: `channels/`,
      data,
      params: {
        user_id: id,
      },
    }).then((response) => response.data);
  },

  updateMyChanel(id, data, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "PATCH",
      url: `channels/${id}`,
      data,
    }).then((response) => response.data);
  },

  deleteChanel(id, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "DELETE",
      url: `channels/${id}`,
    });
  },

  updateMe(data, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "PATCH",
      url: "users/update",
      data,
    }).then((response) => response.data);
  },

  updateUserById(data, token, id) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "PATCH",
      url: `users/${id}`,
      data,
    }).then((response) => response.data);
  },

  create(data, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "POST",
      url: "/users/",
      data,
    });
  },

  delete(id, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "DELETE",
      url: `/users/${id}`,
    }).then((response) => response.data);
  },

  banUserById(id, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "PATCH",
      url: `/users/${id}/block`,
    }).then((response) => response.data);
  },
  unbanUserById(id, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "PATCH",
      url: `/users/${id}/unblock`,
    }).then((response) => response.data);
  },
});
