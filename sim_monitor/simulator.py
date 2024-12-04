class Simulator:
    def __init__(self, name, x, y, canvas, images):
        self.name = name
        self.x = x
        self.y = y
        self.canvas = canvas
        self.images = images
        self.ramp_state = 0
        self.motion_state = 0
        self.status = 0
        self.elements = []

    def update_state(self, ramp_state, motion_state, status):
        self.ramp_state = ramp_state
        self.motion_state = motion_state
        self.status = status
        self.draw()

    def draw(self):
        # Clear previous drawings
        for element in self.elements:
            self.canvas.delete(element)
        self.elements.clear()

        # Add padding values
        padding_x = 40  # Horizontal padding
        padding_y = 20  # Horizontal padding
        title_offset = 50
        image_offset = 210
        motion_status_offset = 340 + padding_y
        ramp_status_offset = 380 + padding_y
        status_offset = 420 + padding_y

        # Draw Simulator Name (Centered Above the Image)
        self.elements.append(
            self.canvas.create_text(
                self.x + 120 + padding_x, self.y + title_offset,
                text=self.name,
                font=("Helvetica", 18, "bold"),
                fill="black",
                anchor="center"
            )
        )

        # Determine motion image
        motion_image = self.images["motion_on"] if self.motion_state else self.images["motion_off"]

        # Draw Motion Image (Centered)
        self.elements.append(
            self.canvas.create_image(
                self.x + 120 + padding_x, self.y + image_offset,
                anchor="center",
                image=motion_image
            )
        )

        # Draw Motion Status Label and Indicator
        motion_text_x = self.x + 165 + padding_x
        motion_circle_x = self.x + 185 + padding_x
        self.elements.append(
            self.canvas.create_text(
                motion_text_x, self.y + motion_status_offset,
                text="Motion Status:",
                font=("Helvetica", 14),
                fill="black",
                anchor="e"
            )
        )
        motion_color = "red" if self.motion_state == 1 else "green"
        self.elements.append(
            self.canvas.create_oval(
                motion_circle_x - 10, self.y + motion_status_offset - 10,
                motion_circle_x + 10, self.y + motion_status_offset + 10,
                fill=motion_color,
                outline="black",
                width=2
            )
        )

        # Draw Ramp Status Label and Indicator
        ramp_text_x = self.x + 165 + padding_x
        ramp_circle_x = self.x + 185 + padding_x
        self.elements.append(
            self.canvas.create_text(
                ramp_text_x, self.y + ramp_status_offset,
                text="Ramp Status:",
                font=("Helvetica", 14),
                fill="black",
                anchor="e"
            )
        )
        ramp_color = "green" if self.ramp_state == 0 else "red"
        self.elements.append(
            self.canvas.create_oval(
                ramp_circle_x - 10, self.y + ramp_status_offset - 10,
                ramp_circle_x + 10, self.y + ramp_status_offset + 10,
                fill=ramp_color,
                outline="black",
                width=2
            )
        )

        # Draw Status Text (Centered Below the Ramp Indicator)
        self.elements.append(
            self.canvas.create_text(
                self.x + 120 + padding_x, self.y + status_offset,
                text="Connected" if self.status else "No Data",
                font=("Helvetica", 14),
                fill="black",
                anchor="center"
            )
        )
