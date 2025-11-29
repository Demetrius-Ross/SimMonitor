class Simulator:
    def __init__(self, device_id, name, x, y, canvas, images, scale=1.0):
        self.device_id = device_id
        self.name = name
        self.x = x
        self.y = y
        self.canvas = canvas
        self.images = images
        self.scale = scale


        # Default states
        self.ramp_state = 0
        self.motion_state = 0

        # Mark as offline by default (for pre-populated simulators)
        self.offline = True

        self.elements = []

    def update_state(self, ramp_state, motion_state):
        """Updates ramp/motion and marks the simulator as 'online' (offline=False)."""
        self.ramp_state = ramp_state
        self.motion_state = motion_state
        self.offline = False  # receiving data => 'online'
        self.draw()

        print(f"🎨 Simulator Updated: {self.name} (ID={self.device_id}), "
              f"Ramp={self.ramp_state}, Motion={self.motion_state}, offline={self.offline}")

    def set_offline(self, is_offline=True):
        """Explicitly mark the simulator as offline or online, then redraw."""
        self.offline = is_offline
        self.draw()

        state_str = "OFFLINE" if is_offline else "ONLINE"
        print(f"🔴 Simulator {self.name} (ID={self.device_id}) => {state_str}")

    def draw(self):
        # 1) Clear previous drawings
        for element in self.elements:
            self.canvas.delete(element)
        self.elements.clear()
        

        # 2) Layout constants
        scale = self.scale
        padding_x = int(50 * scale)
        padding_y = int(20 * scale)
        title_offset = int(50 * scale)
        image_offset = int(240 * scale)
        motion_status_offset = int(400 * scale + padding_y)
        ramp_status_offset = int(440 * scale + padding_y)

        # 3) Draw Simulator Name
        self.elements.append(
            self.canvas.create_text(
                self.x + int(120 * scale) + padding_x,
                self.y + title_offset,
                text=self.name,
                font=("Helvetica", int(28 * scale), "bold"),
                fill="black",
                anchor="center"
            )
        )

        # 4) Determine motion image
        if self.motion_state == 2:  # "Up"
            motion_image_key = "motion_up"
        else:                       # "Down" or "In Motion"
            motion_image_key = "motion_down"

        print(f"Motion State: {self.motion_state}, Image Key: {motion_image_key}")

        motion_image = self.images.get(motion_image_key, None)
        if motion_image:
            # Draw the motion image
            self.elements.append(
                self.canvas.create_image(
                    self.x + int(120 * scale) + padding_x,
                    self.y + image_offset,
                    anchor="center",
                    image=motion_image
                )
            )
        else:
            # If no image found, fallback text
            print(f"Warning: Image for '{motion_image_key}' not found.")
            self.elements.append(
                self.canvas.create_text(
                    self.x + int(120 * scale) + padding_x,
                    self.y + image_offset,
                    text="No Image",
                    font=("Helvetica", int(14 * scale), "italic"),
                    fill="gray",
                    anchor="center"
                )
            )

        # 5) If offline => show big red "DISCONNECTED" overlay and return (no statuses)
        if self.offline:
            self._draw_offline_ui()
            return

        # 6) If online => draw motion/ramp statuses
        #    Motion color: 1 => green, 2 => red, 0 => orange
        if self.motion_state == 1:
            motion_color = "green"
        elif self.motion_state == 2:
            motion_color = "red"
        else:
            motion_color = "orange"

        self._draw_status_label_and_indicator(
            "Motion Status:",
            motion_color,
            self.x + int(220 * scale) + padding_x,
            self.y + motion_status_offset
        )

        # 7) Ramp color: 2 => green, 1 => red, 0 => orange
        if self.ramp_state == 2:
            ramp_color = "green"
        elif self.ramp_state == 1:
            ramp_color = "red"
        else:
            ramp_color = "orange"

        self._draw_status_label_and_indicator(
            "Ramp Status:",
            ramp_color,
            self.x + int(220 * scale) + padding_x,
            self.y + ramp_status_offset
        )

    def _draw_offline_ui(self):
        scale = self.scale
        center_x = self.x + int(170 * scale)
        center_y = self.y + int(430 * scale)
        offset = int(18 * scale)

        self.elements.append(
            self.canvas.create_line(
                self.x + offset, self.y + int(60 * scale),
                self.x + int(300 * scale) + offset, self.y + int(400 * scale),
                fill="red", width=int(10 * scale)
            )
        )
        self.elements.append(
            self.canvas.create_line(
                self.x + int(300 * scale) + offset, self.y + int(60 * scale),
                self.x + offset, self.y + int(400 * scale),
                fill="red", width=int(10 * scale)
            )
        )
        self.elements.append(
            self.canvas.create_text(
                center_x, center_y,
                text="DISCONNECTED",
                font=("Helvetica", int(24 * scale), "bold"),
                fill="red",
                anchor="center"
            )
        )

    def _draw_status_label_and_indicator(self, label, color, text_x, indicator_y):
        scale = self.scale
        circle_x = text_x + int(30 * scale)

        self.elements.append(
            self.canvas.create_text(
                text_x,
                indicator_y,
                text=label,
                font=("Helvetica", int(24 * scale), "bold"),
                fill="black",
                anchor="e"
            )
        )
        self.elements.append(
            self.canvas.create_oval(
                circle_x - int(15 * scale),
                indicator_y - int(15 * scale),
                circle_x + int(15 * scale),
                indicator_y + int(15 * scale),
                fill=color,
                outline="black",
                width=int(2.5 * scale)
            )
        )