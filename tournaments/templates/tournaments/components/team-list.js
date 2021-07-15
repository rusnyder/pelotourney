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

function deleteTeam(team_id) {
  $.ajax({
    type: "DELETE",
    url: "{% url 'tournaments:teams' tournament.id %}",
    data: team_id,
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

function addRide(rideId) {
  $.ajax({
    url: "{% url 'tournaments:rides' tournament.id %}",
    type: "POST",
    data: JSON.stringify({ ride_id: rideId }),
    contentType: "application/json; charset=utf-8",
    beforeSend: function(xhr) {
      xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'))
    },
    success: function(data) {
      redirectOrRefresh("{% url 'tournaments:edit' tournament.id %}#rides");
    },
  });
}

function deleteRide(rideId) {
  $.ajax({
    type: "DELETE",
    url: "{% url 'tournaments:rides' tournament.id %}",
    data: rideId,
    beforeSend: function(xhr) {
      xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'))
    },
    success: function(data) {
      redirectOrRefresh("{% url 'tournaments:edit' tournament.id %}#rides");
    }
  });
}

function updateRidesModal() {
  const ridesContainer = $("#ride-modal-rides");
  ridesContainer.html(`
    <div class="d-flex justify-content-center">
      <div class="spinner-border text-secondary mx-auto my-5" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
    </div>
  `.trim())
  $.ajax({
    url: "{% url 'tournaments:rides' tournament.id %}",
    type: "GET",
    data: {
      instructor_id: $("#ride-modal-instructor-id").val(),
      duration: $("#ride-modal-duration").val(),
    },
    dataType: "json",
    success: function (data) {
      const instructorMapping = data.instructors.reduce(function(map, obj) {
        map[obj.id] = obj;
        return map;
      }, {});
      ridesContainer.html(`<ul class="list-group py-3"></ul>`);
      $(data.data).each(function() {
        const rideId = this.id;
        const rideTitle = this.title;
        const instructor = instructorMapping[this.instructor_id]
        const instructorName = instructor.name;
        const instructorImageUrl = instructor.image_url;
        const rideTime = luxon.DateTime.fromSeconds(this.scheduled_start_time).toLocaleString(luxon.DateTime.DATETIME_SHORT);
        ridesContainer.find("ul").append(`
          <li class="list-group-item list-group-item-action d-flex flex-row">
            <img class="rounded-circle my-auto me-3"
                 src="${instructorImageUrl}" alt="${instructorName}" width="32" height="32">
            <div class="col text-truncate">
              <div class="text-truncate">${rideTitle}</div>
              <div>
                <small class="text-muted">${instructorName}<i class="bi-dot"></i>${rideTime}</small>
              </div>
            </div>
            <button class="btn btn-link ms-auto text-secondary hover-primary fs-4"
                    onclick="addRide('${rideId}');">
              <i class="bi-plus-circle-fill"></i>
            </button>
          </li>
        `.trim())
      });
    }
  })
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

  $("#add-ride-modal").on("shown.bs.modal", function(event) {
    function selectIsEmpty(select) {
      return select.find(":not(.bs-title-option)").length === 0;
    }
    const instructorsSelect = $("#ride-modal-instructor-id");
    const durationsSelect = $("#ride-modal-duration");

    // The first time we load the modal, load all the filters
    // and populate the rides list once.
    //
    // All other rides list updates will only occur when the
    // filter selectors are updated
    if (selectIsEmpty(instructorsSelect) || selectIsEmpty(durationsSelect)) {
      // Only need to populate filters if they are empty
      $.ajax({
        url: "{% url 'tournaments:ride_filters' tournament.id %}",
        type: "GET",
        dataType: "json",
        success: function (data) {
          // Populate instructors filter
          const instructors = data.filters.find(function (item) {
            return item.name === "instructor_id";
          }).values;
          $(instructors).each(function () {
            const instructorId = this.value;
            const name = this.display_name;
            const imageUrl = this.display_image_url;
            const dataContent = `
              <img class='rounded-circle my-auto me-2'
                   src='${imageUrl}' alt='${name}' width='24' height='24'>
              <span>${name}</span>
            `.trim();
            instructorsSelect.append(`
              <option value="${instructorId}" data-content="${dataContent}"></option>
            `)
          });

          // Populate ride duration filter
          const durations = data.filters.find(function (item) {
            return item.name === "duration";
          }).values;
          $(durations).each(function () {
            const seconds = this.value;
            const displayName = this.display_name;
            durationsSelect.append(`
              <option value="${seconds}">${displayName}</option>
            `)
          });

          // Refresh all the select pickers at once
          instructorsSelect.selectpicker('refresh');
          durationsSelect.selectpicker('refresh');
        }
      });

      updateRidesModal();
    }
  });

  $("#ride-modal-instructor-id").on("changed.bs.select", updateRidesModal);
  $("#ride-modal-duration").on("changed.bs.select", updateRidesModal);
});
