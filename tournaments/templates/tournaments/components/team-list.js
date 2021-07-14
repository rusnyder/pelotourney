function debounce(timeout, func) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}

function redirectOrRefresh(target) {
  const current = `${window.location.pathname}${window.location.hash}`;
  if (current === target) {
    window.location.reload();
  } else {
    window.location.href = target;
  }
}

function saveTeams() {
  const teams = $(".sortable-team").map(function() {
    const teamId = this.id.split("-")[1];
    const usernames = $(this).find(".peloton-username").map(function () {
      return this.innerText;
    }).toArray();
    return {
      "team_id": teamId,
      "usernames": usernames,
    };
  }).toArray();
  $.ajax({
    type: "POST",
    url: "{% url 'tournaments:update_teams' tournament.id %}",
    data: JSON.stringify(teams),
    contentType: "application/json; charset=utf-8",
    beforeSend: function(xhr) {
      xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'))
    },
    success: function(data) {
      redirectOrRefresh("{% url 'tournaments:edit' tournament.id %}#teams");
    }
  });
}

function deleteMember(username) {
  $.ajax({
    type: "DELETE",
    url: "{% url 'tournaments:rider_search' tournament.id %}",
    data: username,
    beforeSend: function(xhr) {
      xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'))
    },
    success: function(data) {
      redirectOrRefresh("{% url 'tournaments:edit' tournament.id %}#teams");
    }
  });
}

window.addEventListener("DOMContentLoaded", function() {
  const elements = document.getElementsByClassName("sortable-team")
  for (let element of elements) {
    new Sortable(element, {
      group: 'teams',
      animation: 150,
      ghostClass: "bg-primary",
      onEnd: function(event) {
        if (event.to.id !== event.from.id) {
          const item = $(event.item);
          const originalTeam = item.attr("data-original-team");
          if (originalTeam === event.to.id) {
            item.removeClass("bg-warning");
          } else {
            if (!item.hasClass("bg-warning")) {
              item.addClass("bg-warning");
            }
            if (originalTeam === undefined) {
              item.attr("data-original-team", event.from.id);
            }
          }
        }
      }
    });
  }

  $("#rider_query").on("input", debounce(250, function () {
    $.ajax({
      url: "{% url 'tournaments:rider_search' tournament.id %}",
      type: "GET",
      data: { "rider_query": $("#rider_query").val() },
      dataType: "json",
      success: function (data) {
        const riderList = $("#rider_list")
        riderList.empty();
        for(let i=0; i<data.length; i++)
        {
          riderList.append(`<option value="${data[i].username}"></option>`);
        }
      }
    });
  }));
});
